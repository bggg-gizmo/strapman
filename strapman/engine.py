"""Resumable, multi-worker GitHub uploads and verified reconstruction."""
from __future__ import annotations

import hashlib
import json
import os
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
from pathlib import Path
from typing import Any, Callable

from .core import (MIB, Journal, Progress, Store, atomic_json, assemble_local,
                   chunk_source, read_json, require_space, safe_filename, sha256_file,
                   validate_manifest, verify_local_chunks)
from .github import GitHub


def _remote_prefix(upload_id: str) -> str:
    return f"strapman-uploads/{upload_id}"


def _public_manifest(manifest: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    result = dict(manifest)
    result["chunks"] = []
    uploaded = session.get("blobs", {})
    for part in manifest["chunks"]:
        sha = uploaded.get(part["filename"])
        if not sha:
            raise ValueError(f"Missing blob hash for {part['filename']}")
        result["chunks"].append({**part, "blob_sha": sha})
    return result


def _remote_readme(manifest: dict[str, Any], session: dict[str, Any]) -> str:
    # No absolute source path, environment, user name, OS details, or tokens.
    name = manifest["name"]
    return (f"# Strapman upload: {name}\n\n"
            f"This directory contains a byte-for-byte chunked upload made by Strapman.\n"
            f"**Filename:** `{name}`  \n"
            f"**File size:** {manifest['size']} bytes  \n"
            f"**SHA-256:** `{manifest['sha256']}`  \n"
            f"**Parts:** {len(manifest['chunks'])}  \n"
            f"**Part size:** {manifest['chunk_mib']} MiB (maximum)\n\n"
            f"The `manifest.json` file records the verified size, SHA-256 and Git blob SHA "
            f"for each numbered part. The original file is reconstructed and verified with "
            f"Strapman's **Restore from GitHub** feature. Do not concatenate the "
            f"JSON manifest; only concatenate the numbered parts in index order.\n\n"
            f"Status: complete. Commit history preserves each published upload batch.\n")


def _git_blob_sha(path: Path, expected_size: int, expected_sha256: str | None = None) -> str:
    """Compute the Git blob object ID from a local file without altering it."""
    git_hash = hashlib.sha1(f"blob {expected_size}\0".encode("ascii"))
    sha256 = hashlib.sha256()
    actual_size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(MIB), b""):
            actual_size += len(block)
            git_hash.update(block)
            sha256.update(block)
    if actual_size != expected_size or (expected_sha256 is not None and sha256.hexdigest() != expected_sha256):
        raise ValueError(f"Local file changed or checksum failed: {path.name}")
    return git_hash.hexdigest()


class JobPaused(InterruptedError):
    """A user-requested, safely checkpointed pause; resumable after reboot."""


def _bounded_results(pool: ThreadPoolExecutor, work: Callable, items, workers: int):
    """Yield completed results without submitting an unbounded number of tasks.

    Jobs can contain tens of thousands of small chunks. Limit in-flight and
    queued futures to twice the worker count, while preserving parallelism.
    A failing future raises to its caller; the executor owns remaining work.
    """
    iterator = iter(items)
    pending = set()
    for _ in range(workers * 2):
        try:
            item = next(iterator)
        except StopIteration:
            break
        pending.add(pool.submit(work, item))
    while pending:
        completed, pending = wait(pending, return_when=FIRST_COMPLETED)
        for future in completed:
            result = future.result()
            try:
                item = next(iterator)
            except StopIteration:
                pass
            else:
                pending.add(pool.submit(work, item))
            yield result


class Engine:
    def __init__(self, github: GitHub, store: Store | None = None, journal: Journal | None = None):
        self.github = github
        self.store = store or Store()
        self.journal = journal or Journal()
        self.cancel = threading.Event()
        self.pause_requested = threading.Event()
        self._session_lock = threading.RLock()

    def abort(self) -> None:
        self.cancel.set()

    def request_pause(self) -> None:
        """Ask the active worker to stop at its next cooperative safety check.

        In-flight HTTP requests are allowed to return. Already committed batches
        remain committed, and all durable local checkpoints remain in place.
        """
        self.pause_requested.set()
        # Shared stop checks inside hashing/splitting/assembly also observe this.
        self.cancel.set()

    def _check_cancel(self) -> None:
        if self.pause_requested.is_set():
            raise JobPaused("Job paused at a recoverable checkpoint")
        if self.cancel.is_set():
            raise InterruptedError("Job cancelled")

    def _notify(self, callback: Progress | None, phase: str, done: int,
                total: int, detail: str) -> None:
        if callback:
            callback(phase, done, max(total, 1), detail)

    def _update(self, upload_id: str, session: dict[str, Any], **values: Any) -> None:
        with self._session_lock:
            session.update(values)
            self.store.save(upload_id, session)

    def upload(self, source: Path, repo: str, branch: str, *, chunk_mib: int = 4,
               workers: int = 4, mode: str = "chunks", remote_path: str = "",
               verify_remote: bool = True, reconstruct: bool = False,
               publish_full: bool = False, callback: Progress | None = None) -> dict:
        """Run one upload at a time across all Strapman windows/processes.

        Parallel chunk workers still run within the single protected job.
        """
        with self.store.job_lock("upload"):
            return self._upload_locked(
                source, repo, branch, chunk_mib=chunk_mib, workers=workers,
                mode=mode, remote_path=remote_path, verify_remote=verify_remote,
                reconstruct=reconstruct, publish_full=publish_full, callback=callback)

    def _upload_locked(self, source: Path, repo: str, branch: str, *, chunk_mib: int = 4,
               workers: int = 4, mode: str = "chunks", remote_path: str = "",
               verify_remote: bool = True, reconstruct: bool = False,
               publish_full: bool = False, callback: Progress | None = None) -> dict:
        """Upload a file via content-addressed blobs and serial branch commits.

        - chunks: parallel remote blob uploads, small batches published sequentially
        - source: cumulative source staging, with an exact final file for <=16 MiB
        - manifest + README are committed only when every part is published
        """
        self.cancel.clear()
        self.pause_requested.clear()
        if not 1 <= workers <= 12:
            raise ValueError("Worker count must be 1–12")
        if mode not in {"chunks", "source"}:
            raise ValueError("Mode must be 'chunks' or 'source'")
        source = Path(source).expanduser().resolve(strict=True)
        self.journal.write("upload", "started", f"Preparing {source.name} for {repo}:{branch}")
        if (mode == "source" or publish_full) and source.stat().st_size > 16 * MIB:
            raise ValueError("Publishing a full file is limited to 16 MiB; use chunk-only mode")
        # A first-run pause can happen while hashing or splitting, before the
        # content-addressed manifest ID exists. Retain an independent restart
        # record so Job History can resume from the original source after reboot.
        preparation_key = hashlib.sha256(
            (str(source) + "\0" + repo + "\0" + branch + "\0" + mode + "\0"
             + remote_path + "\0" + str(chunk_mib) + "\0" + str(bool(publish_full)))
            .encode("utf-8")
        ).hexdigest()[:24]
        preparation_id = "prepare-" + preparation_key
        source_stat = source.stat()
        previous_preparation = self.store.session(preparation_id)
        if previous_preparation.get("status") in {"paused", "interrupted", "preparing"}:
            if (previous_preparation.get("source_size") not in (None, source_stat.st_size)
                    or previous_preparation.get("source_mtime_ns") not in (None, source_stat.st_mtime_ns)):
                raise ValueError("Original source changed after interruption; refusing to resume different bytes")
        preparation = {
            "job_kind": "upload", "status": "preparing", "preparing": True,
            "checkpoint_id": preparation_id, "source": str(source),
            "source_size": source_stat.st_size, "source_mtime_ns": source_stat.st_mtime_ns,
            "repo": repo, "branch": branch, "mode": mode,
            "remote_path": remote_path, "chunk_mib": chunk_mib,
            "workers": workers, "verify_remote": bool(verify_remote),
            "reconstruct": bool(reconstruct), "publish_full": bool(publish_full),
            "name": source.name, "size": source_stat.st_size,
            # Keep the old superseded record visible if an owner explicitly
            # paused or this job survived a crash before staging finished.
            "retain_history": bool(previous_preparation.get("retain_history")) or
                              previous_preparation.get("status") in {"paused", "interrupted"},
        }
        self.store.save(preparation_id, preparation)
        try:
            manifest, root = chunk_source(source, chunk_mib, self.store, callback, self.cancel)
        except InterruptedError as exc:
            if self.pause_requested.is_set():
                self.store.save(preparation_id, {**preparation, "status": "paused"})
                self.journal.write("upload", "paused", "Preparation paused before upload", preparation_id)
                raise JobPaused("Preparation paused; resume it from Job History") from exc
            self.store.save(preparation_id, {**preparation, "status": "failed",
                                              "error": f"{type(exc).__name__}: {exc}"})
            raise
        if self.store.session(preparation_id):
            pending = self.store.session(preparation_id)
            self.store.save(preparation_id, {**pending, "status": "superseded"})
        upload_id = root.name
        if mode == "source" and manifest["size"] > 16 * MIB:
            raise ValueError("Source-staging mode is limited to 16 MiB; use chunk mode for larger files")
        if remote_path:
            remote_path = self._validate_target_path(remote_path)
        else:
            remote_path = f"restored/{manifest['name']}"
        # Content-addressed chunks are shared; each destination gets a distinct,
        # durable upload journal and remote folder. Never cross-resume two repos.
        destination_key = hashlib.sha256(
            f"{repo.lower()}\0{branch}\0{mode}\0{remote_path}".encode("utf-8")
        ).hexdigest()[:12]
        checkpoint_id = f"{upload_id}-{destination_key}"
        prefix = _remote_prefix(checkpoint_id)
        session = self.store.session(checkpoint_id)
        if not session:
            session = {"job_kind": "upload", "repo": repo, "branch": branch, "mode": mode,
                       "remote_path": remote_path, "status": "prepared", "blobs": {},
                       "published": [], "upload_id": upload_id, "checkpoint_id": checkpoint_id,
                       "source": str(source), "chunk_mib": chunk_mib, "name": manifest["name"],
                       "sha256": manifest["sha256"], "size": manifest["size"],
                       "publish_full": bool(publish_full),
                       "workers": workers, "verify_remote": bool(verify_remote),
                       "reconstruct": bool(reconstruct)}
        else:
            if any(session.get(k) != v for k, v in {
                    "repo": repo, "branch": branch, "mode": mode,
                    "remote_path": remote_path, "sha256": manifest["sha256"],
                    "size": manifest["size"]}.items()):
                raise ValueError("Existing checkpoint does not match the requested upload")
        if session.get("repo") != repo or session.get("branch") != branch:
            raise ValueError("Upload session destination mismatch")
        if "publish_full" in session and bool(session["publish_full"]) != bool(publish_full):
            raise ValueError("The full-file publication option changed from the saved job; use the original setting")
        if mode == "source" or publish_full:
            expected_final = _git_blob_sha(source, manifest["size"], manifest["sha256"])
            existing_final = self.github.file_sha(repo, branch, remote_path)
            if existing_final is not None and existing_final != expected_final:
                raise FileExistsError(f"Remote final file conflicts with the selected source: {remote_path}")
        # Reconcile the actual published Git tree with the durable local state.
        # This catches branch changes and recovers commits made just before a crash.
        self._reconcile_remote(root, manifest, session, checkpoint_id, prefix, repo, branch, mode)
        if session.get("status") == "complete":
            # Never publish a duplicate final commit. Confirm that the manifest
            # and independent chunk paths still correspond to the checkpoint.
            manifest_path = f"{prefix}/manifest.json"
            remote_manifest = self.github.read_text(repo, manifest_path, branch)
            expected = _public_manifest(manifest, session)
            if remote_manifest is None or json.loads(remote_manifest[0]) != expected:
                raise ValueError("Completed checkpoint differs from the remote manifest")
            self._check_remote_paths(repo, branch, prefix, expected)
            if mode == "source" or publish_full:
                if self.github.file_sha(repo, branch, remote_path) != expected_final:
                    raise ValueError("Previously completed final file disappeared from GitHub")
            if verify_remote:
                self._verify_remote(repo, branch, prefix, expected, callback, workers)
            self._restore_after_publication(reconstruct, root, manifest, session, checkpoint_id,
                                            repo, branch, prefix, workers, callback)
            self._notify(callback, "complete", 1, 1, "Already published; remote checkpoint verified")
            return dict(session)
        self._update(checkpoint_id, session, status="uploading")
        try:
            if mode == "chunks":
                self._upload_chunks(root, manifest, session, checkpoint_id, prefix,
                                    repo, branch, workers, callback)
            else:
                self._upload_source(root, manifest, session, checkpoint_id, prefix,
                                    repo, branch, remote_path, callback)
            self._check_cancel()
            portable_manifest = _public_manifest(manifest, session)
            validate_manifest(portable_manifest)
            self._check_remote_paths(repo, branch, prefix, portable_manifest)
            if verify_remote:
                self._verify_remote(repo, branch, prefix, portable_manifest, callback, workers)
            self._check_cancel()
            metadata = {
                f"{prefix}/manifest.json": self.github.create_blob(
                    repo, (json.dumps(portable_manifest, indent=2, sort_keys=True) + "\n").encode()),
                f"{prefix}/README.md": self.github.create_blob(
                    repo, _remote_readme(manifest, session).encode("utf-8")),
            }
            if mode == "source" or publish_full:
                if manifest["size"] > 16 * MIB:
                    raise ValueError("Full-file publication is limited to 16 MiB; chunks remain safe")
                # No final file is committed until every chunk is verified.
                final_blob = self.github.create_blob(repo, source.read_bytes())
                existing_sha = self.github.file_sha(repo, branch, remote_path)
                if existing_sha is not None and existing_sha != final_blob:
                    raise FileExistsError(f"Remote file already exists with different content: {remote_path}")
                metadata[remote_path] = final_blob
            commit = self.github.commit_files(repo, branch, metadata,
                                              f"strapman: complete verified upload {manifest['name']}")
            # A successful API response alone is not enough. Confirm that the
            # manifest and every chunk are still attached to the selected branch.
            self._check_remote_paths(repo, branch, prefix, portable_manifest)
            final_text = self.github.read_text(repo, f"{prefix}/manifest.json", branch)
            if final_text is None or json.loads(final_text[0]) != portable_manifest:
                raise ValueError("Final GitHub manifest was not published correctly")
            if mode == "source" or publish_full:
                if self.github.file_sha(repo, branch, remote_path) != expected_final:
                    raise ValueError("Full GitHub file was not published correctly")
            self._update(checkpoint_id, session, status="complete", final_commit=commit,
                         manifest_path=f"{prefix}/manifest.json")
            self.journal.write("upload", "complete", f"Verified upload {manifest['name']} to {repo}:{branch}", upload_id)
            self._notify(callback, "complete", 1, 1, f"Published manifest and documentation ({commit[:10]})")
            self._restore_after_publication(reconstruct, root, manifest, session, checkpoint_id,
                                            repo, branch, prefix, workers, callback)
            return dict(session)
        except Exception as exc:
            paused = isinstance(exc, InterruptedError) and self.pause_requested.is_set()
            state = "paused" if paused else ("cancelled" if isinstance(exc, InterruptedError) else "failed")
            self._update(checkpoint_id, session, status=state, error=str(exc))
            self.journal.write("upload", state, f"{type(exc).__name__}: {exc}", upload_id)
            if paused:
                raise JobPaused("Upload paused; published chunks and checkpoint preserved") from exc
            raise

    def _restore_after_publication(self, reconstruct: bool, root: Path, manifest: dict[str, Any],
                                   session: dict[str, Any], checkpoint_id: str, repo: str,
                                   branch: str, prefix: str, workers: int,
                                   callback: Progress | None) -> None:
        """Optional restore may fail without undoing a verified GitHub publication.

        A repeat call checks an already reconstructed file by its checksum,
        avoiding duplicate recovery copies. A conflicting local file is never
        overwritten and a unique alternate filename is used instead.
        """
        if not reconstruct:
            return
        target = root / f"remote-restored-{manifest['name']}"
        if target.exists():
            if target.is_file() and target.stat().st_size == manifest["size"] and \
                    sha256_file(target, stop=self.cancel) == manifest["sha256"]:
                self._update(checkpoint_id, session, reconstruction_status="complete",
                             reconstruction_path=str(target), reconstruction_error="")
                self._notify(callback, "assembling", 1, 1, "Previously reconstructed copy verified")
                return
            target = root / f"remote-restored-{manifest['sha256'][:12]}-{manifest['name']}"
        try:
            result = self.restore(repo, branch, f"{prefix}/manifest.json", target,
                                  workers=workers, callback=callback)
        except JobPaused as exc:
            self._update(checkpoint_id, session, reconstruction_status="paused",
                         reconstruction_error=str(exc))
            self.journal.write("restore", "paused", "Optional reconstruction paused; remote upload remains complete",
                               checkpoint_id)
            return
        except Exception as exc:
            # Commit and remote SHA-256 checks have already succeeded. Record
            # a separate local restoration error, not a failed remote upload.
            self._update(checkpoint_id, session, reconstruction_status="failed",
                         reconstruction_error=f"{type(exc).__name__}: {exc}")
            self.journal.write("restore", "failed",
                               f"Optional local reconstruction failed: {type(exc).__name__}: {exc}",
                               checkpoint_id)
            return
        self._update(checkpoint_id, session, reconstruction_status="complete",
                     reconstruction_path=str(result), reconstruction_error="")

    def _reconcile_remote(self, root: Path, manifest: dict[str, Any], session: dict[str, Any],
                          checkpoint_id: str, prefix: str, repo: str, branch: str, mode: str) -> None:
        """Reconcile only branch-attached parts; never trust orphan Git blobs.

        Valid remote parts missing from the local checkpoint are recovered.
        Missing parts previously marked published and changed remote parts stop
        the job rather than silently treating the upload as successful.
        """
        remote = self.github.folder_blobs(repo, branch, f"{prefix}/chunks")
        blobs = dict(session.get("blobs", {}))
        published = set(session.get("published", []))
        valid_names = {part["filename"] for part in manifest["chunks"]}
        if not set(blobs).issubset(valid_names) or not published.issubset(valid_names):
            raise ValueError("Saved checkpoint contains unknown chunk names")
        for part in manifest["chunks"]:
            name = part["filename"]
            published_sha = remote.get(name)
            cached_sha = blobs.get(name)
            if published_sha is None and name in published:
                raise FileNotFoundError(f"Previously published GitHub chunk disappeared: {name}")
            if published_sha is None and cached_sha is None:
                continue
            local_sha = _git_blob_sha(root / "chunks" / name, part["size"], part["sha256"])
            if cached_sha is not None and cached_sha != local_sha:
                raise ValueError(f"Saved Git blob checkpoint disagrees with the source: {name}")
            if published_sha is not None:
                if published_sha != local_sha:
                    raise FileExistsError(f"Conflicting GitHub chunk on {branch}: {name}")
                blobs[name] = local_sha
                published.add(name)
        if mode == "source":
            current_stage = self.github.file_sha(repo, branch, f"{prefix}/staging/{manifest['name']}")
            # Source staging commits are cumulative and sequential. A different
            # remote staging file is not safe to overwrite during resume.
            count = len(published)
            if published != {part["filename"] for part in manifest["chunks"][:count]}:
                raise ValueError("Source stages are non-contiguous; manual review required")
            if count:
                expected_size = sum(part["size"] for part in manifest["chunks"][:count])
                h = hashlib.sha1(f"blob {expected_size}\0".encode("ascii"))
                for part in manifest["chunks"][:count]:
                    with (root / "chunks" / part["filename"]).open("rb") as reader:
                        for block in iter(lambda: reader.read(MIB), b""):
                            h.update(block)
                if current_stage != h.hexdigest():
                    raise ValueError("Remote cumulative source stage differs from saved chunks")
            elif current_stage is not None:
                raise FileExistsError("Unexpected remote cumulative source stage already exists")
        if blobs != session.get("blobs", {}) or published != set(session.get("published", [])):
            self._update(checkpoint_id, session, blobs=blobs, published=sorted(published))
            self.journal.write("upload", "reconciled",
                               f"Recovered {len(published)} published GitHub chunks", checkpoint_id)

    def _check_remote_paths(self, repo: str, branch: str, prefix: str,
                            manifest: dict[str, Any]) -> None:
        remote = self.github.folder_blobs(repo, branch, f"{prefix}/chunks")
        for part in manifest["chunks"]:
            if remote.get(part["filename"]) != part["blob_sha"]:
                raise ValueError(f"GitHub branch is missing or has changed chunk {part['filename']}")

    def audit_session(self, session: dict[str, Any], *, workers: int = 4,
                      callback: Progress | None = None) -> dict[str, Any]:
        """Read-only integrity inventory: prove which chunks are on the GitHub branch.

        A Git blob created by the API is not a published upload until a branch
        points to it. A complete result also requires the matching manifest.
        """
        if not 1 <= workers <= 12:
            raise ValueError("Worker count must be 1–12")
        repo = session["repo"]
        branch = session["branch"]
        checkpoint_id = session["checkpoint_id"]
        upload_id = session["upload_id"]
        manifest = read_json(self.store.folder(upload_id) / "manifest.json")
        validate_manifest(manifest)
        if manifest["sha256"] != session["sha256"] or manifest["size"] != session["size"]:
            raise ValueError("Local manifest does not match the selected upload checkpoint")
        prefix = _remote_prefix(checkpoint_id)
        remote = self.github.folder_blobs(repo, branch, f"{prefix}/chunks")
        remote_parts = [part for part in manifest["chunks"] if part["filename"] in remote]
        verified = 0
        total = manifest["size"]

        def check(part: dict[str, Any]) -> tuple[str, str, int]:
            sha = remote[part["filename"]]
            data = self.github.get_blob(repo, sha)
            if len(data) != part["size"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise ValueError(f"Published GitHub chunk has a SHA-256 mismatch: {part['filename']}")
            return part["filename"], sha, len(data)

        checked: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for name, sha, length in _bounded_results(pool, check, remote_parts, workers):
                checked[name] = sha
                verified += length
                self._notify(callback, "verify", verified, total,
                             f"Verified {len(checked)}/{len(manifest['chunks'])} committed GitHub chunks")
        complete = len(checked) == len(manifest["chunks"])
        read = self.github.read_text(repo, f"{prefix}/manifest.json", branch)
        manifest_present = read is not None
        if manifest_present:
            if not complete:
                raise ValueError("Remote manifest claims a completed upload but chunks are missing")
            portable = dict(manifest)
            portable["chunks"] = [{**part, "blob_sha": checked[part["filename"]]}
                                  for part in manifest["chunks"]]
            if json.loads(read[0]) != portable:
                raise ValueError("Remote manifest does not match verified GitHub chunks")
        complete = complete and manifest_present
        if complete and (session.get("mode") == "source" or session.get("publish_full")):
            # A remote-only audit must work even if local cache parts were
            # removed. Full-file publication is capped at 16 MiB, so verify
            # the actual committed Git blob independently of local state.
            full_sha = self.github.file_sha(repo, branch, session["remote_path"])
            if not full_sha:
                raise ValueError("Published full source file is absent")
            payload = self.github.get_blob(repo, full_sha)
            if len(payload) != manifest["size"] or hashlib.sha256(payload).hexdigest() != manifest["sha256"]:
                raise ValueError("Published full source file has a SHA-256 mismatch")
        self._notify(callback, "committing", 1 if manifest_present else 0, 1,
                     "Final manifest is committed" if manifest_present else "Final manifest not yet committed")
        self._notify(callback, "verify", verified, total,
                     "Remote audit complete" if complete else "Remote upload incomplete; verified chunks retained")
        return {"repo": repo, "branch": branch, "verified_parts": len(checked),
                "total_parts": len(manifest["chunks"]), "verified_bytes": verified,
                "total_bytes": total, "manifest_present": manifest_present, "complete": complete,
                "remote_prefix": prefix}

    @staticmethod
    def _validate_target_path(path: str) -> str:
        path = path.strip().strip("/")
        if not path or any(p in ("", ".", "..") for p in path.split("/")) or "\\" in path or "\0" in path:
            raise ValueError("Invalid GitHub file path")
        if path.startswith(".git/"):
            raise ValueError("Git internals cannot be a remote target")
        return path

    def _check_target_absent(self, repo: str, branch: str, path: str) -> None:
        if self.github.file_sha(repo, branch, path) is not None:
            raise FileExistsError(f"GitHub destination already exists: {path}")

    def _upload_chunks(self, root: Path, manifest: dict, session: dict, checkpoint_id: str,
                       prefix: str, repo: str, branch: str, workers: int, callback: Progress | None) -> None:
        chunks = manifest["chunks"]
        uploaded: dict[str, str] = session.setdefault("blobs", {})
        published: set[str] = set(session.setdefault("published", []))
        total = manifest["size"]
        done = sum(p["size"] for p in chunks if p["filename"] in uploaded)
        self._notify(callback, "uploading", done, total, "Resuming saved chunk uploads")

        def send(part: dict) -> tuple[str, str, int]:
            self._check_cancel()
            path = root / "chunks" / part["filename"]
            raw = path.read_bytes()
            if len(raw) != part["size"] or hashlib.sha256(raw).hexdigest() != part["sha256"]:
                raise ValueError(f"Chunk changed during transfer: {part['filename']}")
            sha = self.github.create_blob(repo, raw)
            return part["filename"], sha, len(raw)

        # Work in bounded batches: independent blob uploads run in parallel,
        # followed by one serialized branch update per batch.
        for offset in range(0, len(chunks), workers):
            self._check_cancel()
            batch = chunks[offset: offset + workers]
            missing = [p for p in batch if p["filename"] not in uploaded]
            if missing:
                with ThreadPoolExecutor(max_workers=min(workers, len(missing))) as pool:
                    futures = [pool.submit(send, p) for p in missing]
                    for future in as_completed(futures):
                        name, sha, length = future.result()
                        with self._session_lock:
                            uploaded[name] = sha
                            done += length
                            self._update(checkpoint_id, session, blobs=uploaded)
                        self._notify(callback, "uploading", done, total, f"Uploaded {name} (Git blob {sha[:10]})")
            needs_publish = [p for p in batch if p["filename"] not in published]
            if needs_publish:
                entries = {f"{prefix}/chunks/{p['filename']}": uploaded[p["filename"]] for p in needs_publish}
                commit = self.github.commit_files(repo, branch, entries,
                                                  f"strapman: {manifest['name']} chunks "
                                                  f"{offset + 1}-{offset + len(batch)}/{len(chunks)}")
                with self._session_lock:
                    published.update(p["filename"] for p in needs_publish)
                    self._update(checkpoint_id, session, published=sorted(published), last_commit=commit)
                self._notify(callback, "committing", len(published), len(chunks),
                             f"Published batch {offset // workers + 1}; commit {commit[:10]}")

    def _upload_source(self, root: Path, manifest: dict, session: dict, checkpoint_id: str,
                       prefix: str, repo: str, branch: str, target_path: str,
                       callback: Progress | None) -> None:
        """Commit increasingly complete byte-exact source into a staging path."""
        cumulative = bytearray()
        done = 0
        stage_path = f"{prefix}/staging/{manifest['name']}"
        published = set(session.setdefault("published", []))
        for part in manifest["chunks"]:
            self._check_cancel()
            raw = (root / "chunks" / part["filename"]).read_bytes()
            if len(raw) != part["size"] or hashlib.sha256(raw).hexdigest() != part["sha256"]:
                raise ValueError("Source segment checksum failed")
            cumulative.extend(raw)
            done += len(raw)
            if part["filename"] not in session["blobs"]:
                sha = self.github.create_blob(repo, raw)
                session["blobs"][part["filename"]] = sha
                self._update(checkpoint_id, session, blobs=session["blobs"])
            if part["filename"] not in published:
                stage_sha = self.github.create_blob(repo, bytes(cumulative))
                # The cumulative staging file is intentionally replaced on each
                # pass. The immutable part must never be replaced with a new blob.
                chunk_path = f"{prefix}/chunks/{part['filename']}"
                existing = self.github.file_sha(repo, branch, chunk_path)
                if existing is not None and existing != session["blobs"][part["filename"]]:
                    raise FileExistsError(f"Conflicting remote chunk: {chunk_path}")
                self.github.commit_files(
                    repo, branch,
                    {stage_path: stage_sha, chunk_path: session["blobs"][part["filename"]]},
                    f"strapman: stage {manifest['name']} source bytes {done}/{manifest['size']}",
                    replace_paths={stage_path})
                published.add(part["filename"])
                self._update(checkpoint_id, session, published=sorted(published))
            self._notify(callback, "uploading", done, manifest["size"],
                         f"Source stage {part['index'] + 1}/{len(manifest['chunks'])}")
        if hashlib.sha256(cumulative).hexdigest() != manifest["sha256"]:
            raise ValueError("Cumulative staged source checksum mismatch")

    def _verify_remote(self, repo: str, branch: str, prefix: str,
                       manifest: dict[str, Any], callback: Progress | None,
                       workers: int) -> None:
        self._check_remote_paths(repo, branch, prefix, manifest)
        total = manifest["size"]
        done = 0

        def check(part: dict) -> int:
            self._check_cancel()
            data = self.github.get_blob(repo, part["blob_sha"])
            if len(data) != part["size"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
                raise ValueError(f"Remote verification failed: {part['filename']}")
            return len(data)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for verified_length in _bounded_results(pool, check, manifest["chunks"], workers):
                done += verified_length
                self._notify(callback, "verify", done, total,
                             f"SHA-256 verified {done:,}/{total:,} remote bytes")

    def restore(self, repo: str, branch: str, manifest_path: str, destination: Path,
                *, workers: int = 4, callback: Progress | None = None) -> Path:
        """Download and restore with a single local reconstruction owner."""
        with self.store.job_lock("restore"):
            return self._restore_locked(repo, branch, manifest_path, destination,
                                        workers=workers, callback=callback)

    def discover_builds(self, repo: str, branch: str) -> list[str]:
        """Find committed Strapman manifests without requiring local history."""
        return self.github.list_strapman_manifests(repo, branch)

    def rebuild_from_github(self, repo: str, branch: str, manifest_path: str,
                            destination: Path, *, workers: int = 4,
                            callback: Progress | None = None) -> Path:
        """First-class remote Build/Rebuild, using the durable restore engine.

        This is intentionally not an upload strategy. It works when the local
        original and the original upload checkpoint are unavailable.
        """
        if (not manifest_path.startswith("strapman-uploads/")
                or not manifest_path.endswith("/manifest.json")
                or len(manifest_path.split("/")) != 3):
            raise ValueError("Select a Strapman GitHub manifest under strapman-uploads/")
        return self.restore(repo, branch, manifest_path, destination,
                            workers=workers, callback=callback)

    def rebuild_local(self, manifest_path: Path, cache_dir: Path, destination: Path,
                      *, callback: Progress | None = None) -> Path:
        """Offline Build/Rebuild with checksum validation and a durable pause state.

        `cache_dir` contains the chunks/ directory. The original source is not
        required. A paused attempt is restartable after reboot, and an existing
        destination is never overwritten.
        """
        with self.store.job_lock("restore"):
            self.cancel.clear()
            self.pause_requested.clear()
            manifest_path = Path(manifest_path).expanduser().resolve(strict=True)
            cache_dir = Path(cache_dir).expanduser().resolve(strict=True)
            destination = Path(destination).expanduser().resolve()
            if destination.exists():
                raise FileExistsError(f"Destination already exists: {destination}")
            manifest = read_json(manifest_path)
            validate_manifest(manifest)
            checkpoint_id = "restore-local-" + hashlib.sha256(
                (str(manifest_path) + "\0" + str(cache_dir) + "\0" + str(destination))
                .encode("utf-8")).hexdigest()[:24]
            session = dict(self.store.session(checkpoint_id))
            if not session:
                session = {"job_kind": "restore-local", "checkpoint_id": checkpoint_id,
                           "manifest_file": str(manifest_path), "cache_dir": str(cache_dir),
                           "destination": str(destination), "name": manifest["name"],
                           "size": manifest["size"], "sha256": manifest["sha256"]}
            if session.get("sha256") != manifest["sha256"] or session.get("size") != manifest["size"]:
                raise ValueError("Local manifest differs from the existing rebuild checkpoint")
            self._update(checkpoint_id, session, status="assembling")
            try:
                self._check_cancel()
                output = assemble_local(cache_dir, manifest, destination, callback, self.cancel)
                self._update(checkpoint_id, session, status="complete", error="")
                self.journal.write("rebuild", "complete", f"Locally rebuilt and verified {manifest['name']}")
                self._notify(callback, "complete", 1, 1, "Build verified and saved")
                return output
            except Exception as exc:
                paused = isinstance(exc, InterruptedError) and self.pause_requested.is_set()
                state = "paused" if paused else ("cancelled" if isinstance(exc, InterruptedError) else "failed")
                self._update(checkpoint_id, session, status=state, error=str(exc))
                self.journal.write("rebuild", state, f"{type(exc).__name__}: {exc}", checkpoint_id)
                if paused:
                    raise JobPaused("Local rebuild paused; verified source parts are retained") from exc
                raise

    def _restore_locked(self, repo: str, branch: str, manifest_path: str, destination: Path,
                        *, workers: int = 4, callback: Progress | None = None) -> Path:
        """Recover from durable downloaded parts, including after process reboot.

        The remote manifest and every cached part are revalidated. Reconstruction
        publishes only after complete SHA-256 verification and never overwrites.
        """
        self.cancel.clear()
        self.pause_requested.clear()
        if not 1 <= workers <= 12:
            raise ValueError("Worker count must be 1–12")
        destination = Path(destination).expanduser().resolve()
        if destination.exists():
            raise FileExistsError(f"Destination already exists: {destination}")
        resume_key = hashlib.sha256(
            (repo + "\0" + branch + "\0" + manifest_path + "\0" + str(destination))
            .encode("utf-8")
        ).hexdigest()[:24]
        checkpoint_id = "restore-job-" + resume_key
        previous = self.store.session(checkpoint_id)
        if previous and any(previous.get(key) != value for key, value in {
                "repo": repo, "branch": branch, "manifest_path": manifest_path,
                "destination": str(destination)}.items()):
            raise ValueError("Restore checkpoint does not match the requested destination")
        session = dict(previous) if previous else {
            "job_kind": "restore", "checkpoint_id": checkpoint_id,
            "repo": repo, "branch": branch, "manifest_path": manifest_path,
            "destination": str(destination), "workers": workers,
            "status": "preparing", "name": destination.name,
        }
        self.store.save(checkpoint_id, session)
        try:
            read = self.github.read_text(repo, manifest_path, branch)
            self._check_cancel()
            if read is None:
                raise FileNotFoundError(f"No manifest at {repo}:{branch}/{manifest_path}")
            manifest = json.loads(read[0])
            validate_manifest(manifest)
            for part in manifest["chunks"]:
                if "blob_sha" not in part:
                    raise ValueError("Manifest lacks Git blob reference")
            # A fetchable Git object is not necessarily still committed. A
            # standard Strapman build also requires each part to remain
            # attached to the selected branch, not merely available by SHA.
            if (manifest_path.startswith("strapman-uploads/")
                    and manifest_path.endswith("/manifest.json")
                    and len(manifest_path.split("/")) == 3):
                self._check_remote_paths(repo, branch,
                                         manifest_path.removesuffix("/manifest.json"), manifest)
            if previous and previous.get("sha256") not in (None, manifest["sha256"]):
                raise ValueError("Remote restore manifest differs from saved checkpoint")
            self._update(checkpoint_id, session, status="downloading",
                         sha256=manifest["sha256"], size=manifest["size"], name=manifest["name"])
            uid = f"restore-{manifest['sha256'][:20]}"
            root = self.store.folder(uid)
            chunks = root / "chunks"
            require_space(root, manifest["size"])
            require_space(destination.parent, manifest["size"])
            chunks.mkdir(parents=True, exist_ok=True)
            completed = 0

            def fetch(part: dict) -> int:
                self._check_cancel()
                path = chunks / part["filename"]
                if path.exists() and path.stat().st_size == part["size"] and \
                        sha256_file(path, stop=self.cancel) == part["sha256"]:
                    return part["size"]
                content = self.github.get_blob(repo, part["blob_sha"])
                if len(content) != part["size"] or hashlib.sha256(content).hexdigest() != part["sha256"]:
                    raise ValueError(f"Remote chunk corrupted: {part['filename']}")
                self._check_cancel()
                temporary = path.with_suffix(".incomplete")
                with temporary.open("wb") as out:
                    out.write(content)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, path)
                return len(content)

            with ThreadPoolExecutor(max_workers=workers) as pool:
                for verified_length in _bounded_results(pool, fetch, manifest["chunks"], workers):
                    completed += verified_length
                    self._notify(callback, "downloading", completed, manifest["size"],
                                 f"Received and verified {completed:,} bytes")
            self._check_cancel()
            result = assemble_local(root, manifest, destination, callback, self.cancel)
            self._update(checkpoint_id, session, status="complete", error="")
            self.journal.write("restore", "complete", f"Restored and SHA-256 verified {manifest['name']}")
            self._notify(callback, "complete", 1, 1, "Reconstruction verified and saved")
            return result
        except Exception as exc:
            paused = isinstance(exc, InterruptedError) and self.pause_requested.is_set()
            state = "paused" if paused else ("cancelled" if isinstance(exc, InterruptedError) else "failed")
            self._update(checkpoint_id, session, status=state, error=str(exc))
            self.journal.write("restore", state, f"{type(exc).__name__}: {exc}", checkpoint_id)
            if paused:
                raise JobPaused("Restore paused; cached verified chunks and destination preserved") from exc
            raise
