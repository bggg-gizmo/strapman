"""Strapman core: persistent settings, integrity, partitioning and journals.

No local machine identifiers, absolute source paths or tokens are included in
manifests destined for GitHub. Runtime state stays in OS app-data directories.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
import platform
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import urlparse

APP_NAME = "Strapman"
VERSION = "0.5.2-dev"
SCHEMA_VERSION = 1
MIB = 1024 * 1024
Progress = Callable[[str, int, int, str], None]


def app_directory() -> Path:
    override = os.environ.get("STRAPMAN_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    from .editions import BOOTLEGGER, active_edition
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        base = Path(root) / APP_NAME
    else:
        root = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        base = Path(root) / "strapman"
    return base / BOOTLEGGER if active_edition() == BOOTLEGGER else base


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
        # On POSIX, a synced file alone does not durably record its directory
        # entry across a sudden power cut. Sync the parent where supported.
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def read_json(path: Path, fallback: dict | None = None) -> dict[str, Any]:
    if not path.is_file():
        return dict(fallback or {})
    with path.open("r", encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise ValueError(f"Invalid JSON object in {path.name}")
    return result


DEFAULT_SETTINGS: dict[str, Any] = {
    "chunk_mib": 4,
    "workers": 4,
    "sound_enabled": True,
    "voice_enabled": True,
    "theme_mode": "Purple Night",
    "flash_enabled": True,
    "verify_remote_after_upload": True,
    "reconstruct_after_upload": True,
    "rebuild_workflow_v052": True,
    "publish_full_if_possible": False,
    "last_repo": "",
    "last_branch": "main",
    "repo_favorites": [],
    "onboarded": False,
    "oauth_client_id": "",
    "auth_method": "",
    "auth_login": "",
}


class Settings:
    def __init__(self, root: Path | None = None):
        self.root = root or app_directory()
        self.path = self.root / "settings.json"
        self._lock = threading.RLock()
        saved = read_json(self.path)
        self.data = {**DEFAULT_SETTINGS, **saved}
        # Older installs inherited an upload-only default. Move them to the
        # complete automated workflow once; later user opt-outs are respected.
        if not saved.get("rebuild_workflow_v052"):
            self.data["reconstruct_after_upload"] = True
            self.data["rebuild_workflow_v052"] = True
            if saved:
                atomic_json(self.path, self.data)

    def get(self, key: str) -> Any:
        with self._lock:
            return self.data[key]

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULT_SETTINGS:
            raise KeyError(key)
        with self._lock:
            self.data[key] = value
            atomic_json(self.path, self.data)


class Journal:
    """Thread-safe local JSON-lines event journal; never stores secrets."""

    def __init__(self, root: Path | None = None):
        self.root = root or app_directory()
        self.path = self.root / "logs" / "events.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def write(self, action: str, status: str, message: str, session: str = "") -> None:
        entry = {
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "action": action,
            "status": status,
            "message": message,
            "session": session,
        }
        with self._lock, self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def parse_repository(value: str) -> str:
    """Accept owner/repo, GitHub web URL, or GitHub git clone URL."""
    text = value.strip().rstrip("/")
    if text.startswith("git@github.com:"):
        text = text.removeprefix("git@github.com:")
    elif "://" in text:
        url = urlparse(text)
        if url.scheme != "https" or url.hostname != "github.com":
            raise ValueError("Only https://github.com repository URLs are supported")
        text = url.path.strip("/")
    if text.endswith(".git"):
        text = text[:-4]
    parts = text.split("/")
    if len(parts) != 2 or not all(re.fullmatch(r"[A-Za-z0-9_.-]+", p) for p in parts):
        raise ValueError("Repository must be owner/repository or a GitHub repository URL")
    if parts[0] in {".", ".."} or parts[1] in {".", ".."}:
        raise ValueError("Invalid repository path")
    return "/".join(parts)


def safe_filename(value: str) -> str:
    name = Path(value).name
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip(".")
    return cleaned[:130] or "archive"


def sha256_file(file: Path, callback: Progress | None = None, stop: threading.Event | None = None) -> str:
    hash_ = hashlib.sha256()
    total = file.stat().st_size
    complete = 0
    with file.open("rb") as source:
        while True:
            if stop is not None and stop.is_set():
                raise InterruptedError("Job cancelled")
            block = source.read(MIB)
            if not block:
                break
            hash_.update(block)
            complete += len(block)
            if callback:
                callback("hashing", complete, total, "Calculating source checksum")
    return hash_.hexdigest()


def require_space(folder: Path, needed_bytes: int, reserve_mib: int = 128) -> int:
    folder = folder.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(folder).free
    needed = max(0, needed_bytes) + reserve_mib * MIB
    if free < needed:
        raise OSError(f"Insufficient disk space: need {needed / MIB:.1f} MiB; available {free / MIB:.1f} MiB")
    return free


@dataclass(frozen=True)
class Chunk:
    index: int
    filename: str
    size: int
    sha256: str


class JobAlreadyRunning(RuntimeError):
    """Another Strapman process holds the exclusive upload lock."""


# Only live-looking states are eligible for recovery. A completed remote
# publication is never demoted merely because optional reconstruction stopped.
ACTIVE_JOB_STATES = frozenset({
    "preparing", "prepared", "uploading", "published", "downloading", "assembling",
    "verifying", "committing", "running", "pausing",
})


class Store:
    def __init__(self, root: Path | None = None):
        self.root = (root or app_directory()) / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    @contextmanager
    def job_lock(self, name: str):
        """Single-machine, cross-process, fail-closed non-blocking job lock.

        Persistent lock files are harmless. Never delete them to force an unlock:
        operating-system file locks release on process exit or crash.
        """
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
            raise ValueError("Invalid lock name")
        lock_dir = self.root / "locks"
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / (name + ".lock")
        with lock_path.open("a+b") as handle:
            if handle.seek(0, os.SEEK_END) == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            locked = False
            try:
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except (OSError, BlockingIOError) as exc:
                    raise JobAlreadyRunning(
                        "An upload is already running in another Strapman window or process. "
                        "Monitor that job or let it finish before pressing Resume again."
                    ) from exc
                yield
            finally:
                if locked:
                    handle.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def job_is_running(self, name: str) -> bool:
        """Check OS ownership, not PID or a stale timestamp, without killing anything."""
        try:
            with self.job_lock(name):
                return False
        except JobAlreadyRunning:
            return True

    def recover_interrupted_jobs(self) -> list[str]:
        """Label abandoned active jobs only when their OS worker lock is free.

        This never starts work or changes chunk/manifest files. A running worker
        in another Strapman process remains untouched, even if its saved
        checkpoint looks old. Call on desktop startup, not during a transfer.
        """
        recovered: list[str] = []
        for lock_name, kinds in (("upload", {"upload"}),
                                 ("restore", {"restore", "restore-local"})):
            try:
                with self.job_lock(lock_name):
                    for session in self.list_sessions():
                        if (session.get("job_kind", "upload") not in kinds or
                                session.get("status") not in ACTIVE_JOB_STATES):
                            continue
                        checkpoint_id = session["checkpoint_id"]
                        # Re-read under the OS lock so no concurrent owner can
                        # have changed the checkpoint after the listing.
                        current = self.session(checkpoint_id)
                        if current.get("status") not in ACTIVE_JOB_STATES:
                            continue
                        self.save(checkpoint_id, {
                            **current, "status": "interrupted",
                            "error": "Process ended before job completion; resume from verified checkpoints",
                        })
                        recovered.append(checkpoint_id)
            except JobAlreadyRunning:
                continue
        return recovered

    def folder(self, upload_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", upload_id):
            raise ValueError("Invalid upload ID")
        return self.root / upload_id

    def session(self, upload_id: str) -> dict[str, Any]:
        return read_json(self.folder(upload_id) / "session.json")

    def save(self, upload_id: str, session: dict[str, Any]) -> None:
        with self._lock:
            session["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            atomic_json(self.folder(upload_id) / "session.json", session)

    def list_sessions(self) -> list[dict[str, Any]]:
        values = []
        for file in self.root.glob("*/session.json"):
            try:
                row = read_json(file)
                row["checkpoint_id"] = file.parent.name
                # Brand-new preparation records become redundant after their
                # destination checkpoint exists. Preserve them on disk but
                # avoid duplicate history rows. Explicitly paused or
                # interrupted preparations remain inspectable after supersession.
                if (row.get("status") == "superseded" and row.get("preparing")
                        and not row.get("retain_history")):
                    continue
                values.append(row)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
        return sorted(values, key=lambda a: a.get("updated", ""), reverse=True)


def chunk_source(source: Path, chunk_mib: int, store: Store, callback: Progress | None = None,
                 stop: threading.Event | None = None) -> tuple[dict[str, Any], Path]:
    """Split without data loss; store verified chunks and a portable manifest."""
    source = source.expanduser().resolve(strict=True)
    if not source.is_file():
        raise ValueError("Choose a regular file")
    if not 1 <= chunk_mib <= 16:
        raise ValueError("Chunk size must be between 1 and 16 MiB")
    original_size = source.stat().st_size
    if original_size == 0:
        raise ValueError("Empty input files are not supported")
    digest = sha256_file(source, callback, stop)
    upload_id = f"{safe_filename(source.name)[:48]}-{digest[:16]}-{chunk_mib}m"
    root = store.folder(upload_id)
    chunk_dir = root / "chunks"
    old_manifest = root / "manifest.json"
    if old_manifest.exists():
        existing = read_json(old_manifest)
        if (existing.get("sha256") == digest and existing.get("size") == original_size
                and existing.get("chunk_mib") == chunk_mib):
            try:
                verify_local_chunks(root, existing, callback, stop)
                return existing, root
            except (ValueError, FileNotFoundError):
                pass
    require_space(root, original_size)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    pieces: list[dict[str, Any]] = []
    size_limit = chunk_mib * MIB
    completed = 0
    with source.open("rb") as reader:
        index = 0
        while True:
            if stop is not None and stop.is_set():
                raise InterruptedError("Job cancelled")
            chunk_name = f"part-{index:06d}"
            part_path = chunk_dir / chunk_name
            temp_path = part_path.with_suffix(".incomplete")
            checksum = hashlib.sha256()
            written = 0
            with temp_path.open("wb") as writer:
                while written < size_limit:
                    if stop is not None and stop.is_set():
                        raise InterruptedError("Job cancelled")
                    block = reader.read(min(MIB, size_limit - written))
                    if not block:
                        break
                    checksum.update(block)
                    writer.write(block)
                    written += len(block)
                writer.flush()
                os.fsync(writer.fileno())
            if written == 0:
                temp_path.unlink()
                break
            os.replace(temp_path, part_path)
            pieces.append({"index": index, "filename": chunk_name, "size": written,
                           "sha256": checksum.hexdigest()})
            completed += written
            if callback:
                callback("splitting", completed, original_size, f"Split chunk {index + 1}")
            index += 1
    if completed != original_size:
        raise ValueError("Source size changed during splitting")
    if sha256_file(source, stop=stop) != digest:
        raise ValueError("Source changed while splitting; refusing to publish")
    manifest = {
        "format": "strapman-chunks-v1", "schema": SCHEMA_VERSION,
        "name": safe_filename(source.name), "size": original_size,
        "sha256": digest, "chunk_mib": chunk_mib, "chunks": pieces,
    }
    atomic_json(old_manifest, manifest)
    return manifest, root


def verify_local_chunks(root: Path, manifest: dict[str, Any], callback: Progress | None = None,
                        stop: threading.Event | None = None) -> None:
    validate_manifest(manifest)
    written = 0
    for part in manifest["chunks"]:
        if stop is not None and stop.is_set():
            raise InterruptedError("Job cancelled")
        path = root / "chunks" / part["filename"]
        if path.stat().st_size != part["size"] or sha256_file(path, stop=stop) != part["sha256"]:
            raise ValueError(f"Local chunk corrupted: {part['filename']}")
        written += part["size"]
        if callback:
            callback("verify", written, manifest["size"], f"Verified {part['filename']}")


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("format") != "strapman-chunks-v1" or manifest.get("schema") != SCHEMA_VERSION:
        raise ValueError("Unsupported Strapman manifest")
    name = manifest.get("name")
    if not isinstance(name, str) or safe_filename(name) != name:
        raise ValueError("Unsafe filename in manifest")
    sha = manifest.get("sha256")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise ValueError("Invalid source SHA-256")
    parts = manifest.get("chunks")
    if not isinstance(parts, list) or not parts or len(parts) > 100000:
        raise ValueError("Invalid number of chunks")
    total = 0
    seen: set[str] = set()
    for i, part in enumerate(parts):
        if part.get("index") != i or part.get("filename") != f"part-{i:06d}":
            raise ValueError("Chunk numbering is not contiguous")
        if part["filename"] in seen:
            raise ValueError("Duplicate chunk name")
        seen.add(part["filename"])
        if not isinstance(part.get("size"), int) or not 0 < part["size"] <= 16 * MIB:
            raise ValueError("Invalid chunk size")
        if not isinstance(part.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", part["sha256"]):
            raise ValueError("Invalid chunk checksum")
        git_sha = part.get("blob_sha")
        if git_sha is not None and (not isinstance(git_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", git_sha)):
            raise ValueError("Invalid Git blob SHA")
        total += part["size"]
    if total != manifest.get("size"):
        raise ValueError("Manifest total size mismatch")


def assemble_local(root: Path, manifest: dict[str, Any], destination: Path,
                   callback: Progress | None = None, stop: threading.Event | None = None) -> Path:
    """Atomic reconstruction, with whole-file SHA-256 verification before rename."""
    validate_manifest(manifest)
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    require_space(destination.parent, manifest["size"])
    # A unique, exclusive scratch file is created beside the destination.
    # Publishing with os.link is atomic and refuses to overwrite a file that
    # appears during reconstruction (os.replace would overwrite on POSIX).
    fd, scratch_name = tempfile.mkstemp(prefix=".strapman-restore-", suffix=".incomplete", dir=destination.parent)
    incomplete = Path(scratch_name)
    digest = hashlib.sha256()
    done = 0
    try:
        with os.fdopen(fd, "wb") as writer:
            for part in manifest["chunks"]:
                if stop is not None and stop.is_set():
                    raise InterruptedError("Job cancelled")
                source = root / "chunks" / part["filename"]
                part_hash = hashlib.sha256()
                part_size = 0
                with source.open("rb") as stream:
                    for block in iter(lambda: stream.read(MIB), b""):
                        if stop is not None and stop.is_set():
                            raise InterruptedError("Job cancelled")
                        writer.write(block)
                        digest.update(block)
                        part_hash.update(block)
                        part_size += len(block)
                        done += len(block)
                        if callback:
                            callback("assembling", done, manifest["size"], "Reconstructing verified output")
                if part_size != part["size"] or part_hash.hexdigest() != part["sha256"]:
                    raise ValueError(f"Chunk corrupted: {part['filename']}")
            writer.flush()
            os.fsync(writer.fileno())
        if done != manifest["size"] or digest.hexdigest() != manifest["sha256"]:
            raise ValueError("Reconstructed file failed whole-file SHA-256")
        # A pause/stop arriving during the last output block must be honoured
        # before the final verified file becomes visible at its destination.
        if stop is not None and stop.is_set():
            raise InterruptedError("Reconstruction paused or cancelled before publication")
        # Windows os.rename refuses an existing destination, and also works on
        # filesystems without hardlinks. POSIX os.rename would overwrite, so use
        # an exclusive hardlink and fail closed where hardlinks are unavailable.
        if os.name == "nt":
            os.rename(incomplete, destination)
        else:
            os.link(incomplete, destination)
    finally:
        if incomplete.exists():
            incomplete.unlink()
    return destination
