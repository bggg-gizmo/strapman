from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from strapman.core import JobAlreadyRunning, Journal, Store
from strapman.engine import Engine


class FakeGitHub:
    """In-memory fake exercising real split, checkpoint, verification and restore."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.paths: dict[tuple[str, str, str], str] = {}
        self.commit_count = 0
        self.corrupt_fetch = False

    def create_blob(self, repo: str, data: bytes) -> str:
        header = b'blob ' + str(len(data)).encode() + b'\0'
        sha = hashlib.sha1(header + data).hexdigest()
        self.blobs[sha] = data
        return sha

    def get_blob(self, repo: str, sha: str) -> bytes:
        contents = self.blobs[sha]
        if self.corrupt_fetch:
            return bytes([contents[0] ^ 0xFF]) + contents[1:]
        return contents

    def file_sha(self, repo: str, branch: str, path: str) -> str | None:
        return self.paths.get((repo, branch, path))

    def folder_blobs(self, repo: str, branch: str, folder: str) -> dict[str, str]:
        prefix = folder.strip("/") + "/"
        return {path[len(prefix):]: sha for (owner, ref, path), sha in self.paths.items()
                if owner == repo and ref == branch and path.startswith(prefix)
                and "/" not in path[len(prefix):]}

    def commit_files(self, repo: str, branch: str, files: dict[str, str], message: str,
                     *, replace_paths: set[str] | None = None) -> str:
        replace_paths = replace_paths or set()
        for path, sha in files.items():
            previous = self.file_sha(repo, branch, path)
            if previous is not None and previous != sha and path not in replace_paths:
                raise FileExistsError('Remote file differs')
        pending = {path: sha for path, sha in files.items()
                   if self.file_sha(repo, branch, path) != sha}
        if not pending:
            return f'{self.commit_count:040x}'
        for path, sha in pending.items():
            self.paths[(repo, branch, path)] = sha
        self.commit_count += 1
        return f'{self.commit_count:040x}'

    def read_text(self, repo: str, path: str, ref: str = '') -> tuple[str, str] | None:
        sha = self.file_sha(repo, ref, path)
        return (self.blobs[sha].decode('utf-8'), sha) if sha else None


def engine(tmp_path: Path, github: FakeGitHub) -> Engine:
    return Engine(github, Store(tmp_path / 'state'), Journal(tmp_path / 'logs'))


def test_binary_upload_restore_and_resume(tmp_path: Path) -> None:
    repo = 'owner/repo'
    source = tmp_path / 'app.bin'
    source.write_bytes(bytes(range(256)) * 8500)
    fake = FakeGitHub()
    worker = engine(tmp_path, fake)
    callbacks: list[tuple[str, int, int]] = []
    result = worker.upload(source, repo, 'main', chunk_mib=1, workers=3,
                           callback=lambda phase, done, total, detail:
                           callbacks.append((phase, done, total)))
    assert result['status'] == 'complete'
    assert any(phase == 'verify' for phase, done, total in callbacks)
    assert result['manifest_path'] in [k[2] for k in fake.paths]
    manifest, _ = fake.read_text(repo, result['manifest_path'], 'main')
    assert 'private' not in manifest.lower()
    assert str(tmp_path) not in manifest
    assert 'source' not in json.loads(manifest)
    output = tmp_path / 'restored.bin'
    worker.restore(repo, 'main', result['manifest_path'], output, workers=2)
    assert output.read_bytes() == source.read_bytes()
    before = fake.commit_count
    again = worker.upload(source, repo, 'main', chunk_mib=1, workers=3)
    assert again['status'] == 'complete'
    assert fake.commit_count == before


def test_source_mode_keeps_independent_chunks_and_final_file(tmp_path: Path) -> None:
    source = tmp_path / 'module.gd'
    content = b'\x23 Header\n' + b'abcde\n' * 240000
    source.write_bytes(content)
    fake = FakeGitHub()
    result = engine(tmp_path, fake).upload(source, 'owner/repo', 'feature',
                                           chunk_mib=1, workers=4,
                                           mode='source', remote_path='src/module.gd')
    assert fake.blobs[fake.file_sha('owner/repo', 'feature', 'src/module.gd')] == content
    manifest = json.loads(fake.read_text('owner/repo', result['manifest_path'], 'feature')[0])
    assert len(manifest['chunks']) == 2
    for part in manifest['chunks']:
        assert fake.file_sha('owner/repo', 'feature',
                             result['manifest_path'].removesuffix('manifest.json') + 'chunks/' + part['filename'])
    restored = tmp_path / 'again.gd'
    engine(tmp_path, fake).restore('owner/repo', 'feature', result['manifest_path'], restored)
    assert restored.read_bytes() == content


def test_distinct_repo_and_branch_get_distinct_checkpoints(tmp_path: Path) -> None:
    source = tmp_path / 'dataset.bin'
    source.write_bytes(b'z' * 3000)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    first = app.upload(source, 'owner/one', 'main')
    second = app.upload(source, 'owner/two', 'main')
    third = app.upload(source, 'owner/one', 'dev')
    assert len({first['checkpoint_id'], second['checkpoint_id'], third['checkpoint_id']}) == 3
    assert len({first['manifest_path'], second['manifest_path'], third['manifest_path']}) == 3
    assert len(app.store.list_sessions()) == 3


def test_existing_different_final_path_is_not_overwritten(tmp_path: Path) -> None:
    source = tmp_path / 'module.py'
    source.write_bytes(b'print("new")\n')
    fake = FakeGitHub()
    existing = fake.create_blob('owner/repo', b'print("old")\n')
    fake.paths[('owner/repo', 'main', 'src/module.py')] = existing
    with pytest.raises(FileExistsError):
        engine(tmp_path, fake).upload(source, 'owner/repo', 'main', mode='source',
                                     remote_path='src/module.py')
    assert fake.file_sha('owner/repo', 'main', 'src/module.py') == existing


def test_corrupt_remote_blob_does_not_complete(tmp_path: Path) -> None:
    source = tmp_path / 'input.bin'
    source.write_bytes(b'first' * 10000)
    fake = FakeGitHub()
    fake.corrupt_fetch = True
    app = engine(tmp_path, fake)
    with pytest.raises(ValueError, match='Remote verification failed'):
        app.upload(source, 'owner/repo', 'main')
    row = app.store.list_sessions()[0]
    assert row['status'] == 'failed'
    assert not any(k[2].endswith('manifest.json') for k in fake.paths)


def test_duplicate_upload_refused_without_new_commit(tmp_path: Path) -> None:
    source = tmp_path / "bundle.bin"
    source.write_bytes(b"same content" * 300)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    with app.store.job_lock("upload"):
        with pytest.raises(JobAlreadyRunning, match="already running"):
            engine(tmp_path, fake).upload(source, "owner/repo", "main")
    assert fake.commit_count == 0
    assert list((tmp_path / "state" / "jobs").glob("*/manifest.json")) == []
    result = app.upload(source, "owner/repo", "main")
    assert result["status"] == "complete"


def test_lock_released_on_failure(tmp_path: Path) -> None:
    store = Store(tmp_path)
    with pytest.raises(RuntimeError, match="simulated"):
        with store.job_lock("upload"):
            raise RuntimeError("simulated")
    with store.job_lock("upload"):
        pass


def test_lock_blocks_other_process(tmp_path: Path) -> None:
    import subprocess
    import sys

    script = ("from strapman.core import Store, JobAlreadyRunning\n"
              "from pathlib import Path\n"
              "try:\n"
              "    with Store(Path(__import__('sys').argv[1])).job_lock('upload'):\n"
              "        raise SystemExit(9)\n"
              "except JobAlreadyRunning:\n"
              "    raise SystemExit(0)\n")
    with Store(tmp_path).job_lock("upload"):
        child = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                               capture_output=True, text=True)
        assert child.returncode == 0, child.stderr


def test_remote_audit_identifies_partial_and_completed_upload(tmp_path: Path) -> None:
    source = tmp_path / "archive.bin"
    source.write_bytes(b"packets" * 340000)

    class InterruptAfterOneBatch(FakeGitHub):
        def __init__(self):
            super().__init__()
            self.fail_second = True
        def commit_files(self, repo, branch, files, message, *, replace_paths=None):
            if "chunks" in message and self.commit_count >= 1 and self.fail_second:
                self.fail_second = False
                raise ConnectionError("simulated interruption")
            return super().commit_files(repo, branch, files, message, replace_paths=replace_paths)

    fake = InterruptAfterOneBatch()
    app = engine(tmp_path, fake)
    with pytest.raises(ConnectionError, match="simulated interruption"):
        app.upload(source, "owner/repo", "main", chunk_mib=1, workers=1)
    saved = app.store.list_sessions()[0]
    assert saved["checkpoint_id"] != saved["upload_id"]
    assert saved["status"] == "failed"
    partial = app.audit_session(saved, workers=2)
    assert partial["verified_parts"] == 1
    assert partial["total_parts"] == 3
    assert partial["verified_bytes"] == 1024 * 1024
    assert partial["complete"] is False
    assert partial["manifest_present"] is False
    completed = app.upload(source, "owner/repo", "main", chunk_mib=1, workers=1)
    audit = app.audit_session(app.store.list_sessions()[0], workers=3)
    assert completed["status"] == "complete"
    assert audit["verified_parts"] == audit["total_parts"] == 3
    assert audit["verified_bytes"] == audit["total_bytes"] == source.stat().st_size
    assert audit["manifest_present"] is True
    assert audit["complete"] is True


def test_resume_reconciles_committed_remote_parts_after_lost_checkpoint(tmp_path: Path) -> None:
    source = tmp_path / "lost-state.bin"
    source.write_bytes(b"z" * (1024 * 1024 + 13))
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    result = app.upload(source, "owner/repo", "main", chunk_mib=1, workers=1)
    commits = fake.commit_count
    session = app.store.session(result["checkpoint_id"])
    session["status"] = "failed"
    session["blobs"] = {}
    session["published"] = []
    app.store.save(result["checkpoint_id"], session)
    recovered = app.upload(source, "owner/repo", "main", chunk_mib=1, workers=1)
    assert recovered["status"] == "complete"
    assert len(recovered["published"]) == 2
    assert len(recovered["blobs"]) == 2
    assert fake.commit_count == commits


def test_tampered_published_chunk_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "image.bin"
    source.write_bytes(b"secret pixels" * 10000)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    result = app.upload(source, "owner/repo", "main", chunk_mib=1)
    entry = next(path for path in fake.paths if path[2].startswith("strapman-uploads/")
                 and "/chunks/" in path[2])
    original = fake.paths[entry]
    fake.paths[entry] = fake.create_blob("owner/repo", b"changed remotely")
    with pytest.raises(FileExistsError, match="Conflicting GitHub chunk"):
        app.upload(source, "owner/repo", "main", chunk_mib=1)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        app.audit_session(app.store.list_sessions()[0])
    assert fake.paths[entry] != original


def test_deleted_published_chunk_is_not_silently_recreated(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"content" * 2000)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    result = app.upload(source, "owner/repo", "main")
    entry = next(path for path in fake.paths if "/chunks/" in path[2])
    del fake.paths[entry]
    with pytest.raises(FileNotFoundError, match="Previously published"):
        app.upload(source, "owner/repo", "main")
    with pytest.raises(ValueError, match="chunks are missing"):
        app.audit_session(app.store.list_sessions()[0])


def test_final_path_collision_is_detected_before_remote_chunk_commit(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_bytes(b"print(1)\n")
    fake = FakeGitHub()
    fake.paths[("owner/repo", "main", "src/module.py")] = fake.create_blob("owner/repo", b"print(2)\n")
    with pytest.raises(FileExistsError, match="Remote final file conflicts"):
        engine(tmp_path, fake).upload(source, "owner/repo", "main", mode="source",
                                      remote_path="src/module.py")
    assert fake.commit_count == 0


def test_remote_audit_can_run_without_mutating_checkpoints(tmp_path: Path) -> None:
    source = tmp_path / "audit.bin"
    source.write_bytes(b"data" * 1000)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    session = app.upload(source, "owner/repo", "main")
    checkpoint_file = app.store.folder(session["checkpoint_id"]) / "session.json"
    before = checkpoint_file.read_bytes()
    commits = fake.commit_count
    report = app.audit_session(app.store.list_sessions()[0])
    assert report["complete"]
    assert checkpoint_file.read_bytes() == before
    assert fake.commit_count == commits


def test_restore_rejects_duplicate_process(tmp_path: Path) -> None:
    source = tmp_path / "snapshot.bin"
    source.write_bytes(b"abc" * 900)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    uploaded = app.upload(source, "owner/repo", "main")
    with app.store.job_lock("restore"):
        with pytest.raises(JobAlreadyRunning):
            app.restore("owner/repo", "main", uploaded["manifest_path"], tmp_path / "out.bin")
    assert not (tmp_path / "out.bin").exists()


def test_source_mode_recovers_completed_stage_without_rewriting(tmp_path: Path) -> None:
    source = tmp_path / "lexer.gd"
    source.write_bytes(b"fn name()\n" * 140000)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    done = app.upload(source, "owner/repo", "main", mode="source", chunk_mib=1,
                      remote_path="src/lexer.gd")
    commits = fake.commit_count
    session = app.store.session(done["checkpoint_id"])
    session.update({"status": "failed", "blobs": {}, "published": []})
    app.store.save(done["checkpoint_id"], session)
    result = app.upload(source, "owner/repo", "main", mode="source", chunk_mib=1,
                        remote_path="src/lexer.gd")
    assert result["status"] == "complete"
    assert fake.commit_count == commits
    assert app.audit_session(app.store.list_sessions()[0])["complete"]


def test_remote_stage_changed_during_resume_is_not_overwritten(tmp_path: Path) -> None:
    source = tmp_path / "src.gd"
    source.write_bytes(b"x" * (1024 * 1024 + 1))
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    done = app.upload(source, "owner/repo", "main", mode="source", chunk_mib=1,
                      remote_path="src/src.gd")
    stage_path = done["manifest_path"].removesuffix("manifest.json") + "staging/src.gd"
    key = ("owner/repo", "main", stage_path)
    fake.paths[key] = fake.create_blob("owner/repo", b"unexpected replacement")
    before = fake.commit_count
    with pytest.raises(ValueError, match="Remote cumulative source stage differs"):
        app.upload(source, "owner/repo", "main", mode="source", chunk_mib=1,
                   remote_path="src/src.gd")
    assert fake.commit_count == before
    assert fake.blobs[fake.paths[key]] == b"unexpected replacement"


def test_missing_final_commit_manifest_prevents_false_completion(tmp_path: Path) -> None:
    class LostManifest(FakeGitHub):
        def commit_files(self, repo, branch, files, message, *, replace_paths=None):
            sha = super().commit_files(repo, branch, files, message, replace_paths=replace_paths)
            if "complete verified upload" in message:
                for path in files:
                    if path.endswith("manifest.json"):
                        self.paths.pop((repo, branch, path), None)
            return sha

    source = tmp_path / "upload.bin"
    source.write_bytes(b"hello" * 1000)
    fake = LostManifest()
    app = engine(tmp_path, fake)
    with pytest.raises(ValueError, match="Final GitHub manifest"):
        app.upload(source, "owner/repo", "main", verify_remote=False)
    assert app.store.list_sessions()[0]["status"] == "failed"
    assert app.audit_session(app.store.list_sessions()[0])["complete"] is False


def test_audit_requires_remote_blob_download_not_only_manifest(tmp_path: Path) -> None:
    source = tmp_path / "download.bin"
    source.write_bytes(b"abcdef" * 300)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    app.upload(source, "owner/repo", "main")
    fake.corrupt_fetch = True
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        app.audit_session(app.store.list_sessions()[0])


def test_optional_restore_failure_does_not_invalidate_published_upload(tmp_path: Path) -> None:
    source = tmp_path / "backup.bin"
    source.write_bytes(b"verified" * 400)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    original_restore = app.restore
    def no_local_space(*args, **kwargs):
        raise OSError("simulated local reconstruction storage failure")
    app.restore = no_local_space
    result = app.upload(source, "owner/repo", "main", reconstruct=True)
    assert result["status"] == "rebuild_failed"
    assert result["final_commit"]
    assert result["reconstruction_status"] == "failed"
    assert "simulated local" in result["reconstruction_error"]
    assert app.audit_session(app.store.list_sessions()[0])["complete"]
    commits = fake.commit_count
    app.restore = original_restore
    again = app.upload(source, "owner/repo", "main", reconstruct=True)
    assert fake.commit_count == commits
    assert again["status"] == "complete"
    assert again["reconstruction_status"] == "complete"
    assert Path(again["reconstruction_path"]).read_bytes() == source.read_bytes()
    # A third attempt verifies the existing local reconstruction rather than replacing it.
    third = app.upload(source, "owner/repo", "main", reconstruct=True)
    assert third["reconstruction_status"] == "complete"
    assert fake.commit_count == commits


def test_remote_full_source_audit_does_not_require_staging_cache(tmp_path: Path) -> None:
    source = tmp_path / "script.py"
    source.write_bytes(b"print('hi')\n" * 120000)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    result = app.upload(source, "owner/repo", "main", chunk_mib=1, mode="source",
                        remote_path="script.py")
    cache = app.store.folder(result["upload_id"]) / "chunks"
    for part in cache.iterdir():
        part.unlink()
    report = app.audit_session(app.store.list_sessions()[0])
    assert report["complete"]
    assert report["verified_bytes"] == source.stat().st_size
    fake.paths[("owner/repo", "main", "script.py")] = fake.create_blob("owner/repo", b"wrong")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        app.audit_session(app.store.list_sessions()[0])


def test_existing_conflicting_reconstruction_is_preserved(tmp_path: Path) -> None:
    source = tmp_path / "archive.bin"
    source.write_bytes(b"correct" * 250)
    fake = FakeGitHub()
    app = engine(tmp_path, fake)
    result = app.upload(source, "owner/repo", "main")
    content_root = app.store.folder(result["upload_id"])
    target = content_root / "remote-restored-archive.bin"
    target.write_bytes(b"unrelated data; must not be overwritten")
    rebuilt = app.upload(source, "owner/repo", "main", reconstruct=True)
    assert rebuilt["reconstruction_status"] == "complete"
    assert target.read_bytes() == b"unrelated data; must not be overwritten"
    assert Path(rebuilt["reconstruction_path"]).read_bytes() == source.read_bytes()


def test_paused_upload_survives_new_engine_and_preserves_committed_batches(tmp_path: Path) -> None:
    from strapman.engine import JobPaused
    from strapman.core import MIB
    source = tmp_path / "pausable-dataset.bin"
    source.write_bytes(b"x" * (2 * MIB + 41))
    remote = FakeGitHub()
    first = engine(tmp_path, remote)
    def pause_after_first_commit(phase, done, total, detail):
        if phase == "committing" and done >= 1:
            first.request_pause()

    with pytest.raises(JobPaused, match="paused"):
        first.upload(source, "owner/backup", "main", chunk_mib=1, workers=1,
                     callback=pause_after_first_commit)
    paused = first.store.list_sessions()
    assert len(paused) == 1
    assert paused[0]["status"] == "paused"
    assert len(paused[0]["published"]) == 1
    assert remote.commit_count == 1
    # New Engine represents an application restart on a later boot.
    recovered = engine(tmp_path, remote).upload(source, "owner/backup", "main",
                                                    chunk_mib=1, workers=1)
    assert recovered["status"] == "complete"
    assert len(recovered["published"]) == 3
    assert remote.commit_count == 4  # 3 chunk commits plus final manifest.
    assert source.stat().st_size == 2 * MIB + 41


def test_pause_while_hashing_creates_resumable_preparation_job(tmp_path: Path) -> None:
    from strapman.engine import JobPaused
    from strapman.core import MIB
    source = tmp_path / "pausable-preflight.bin"
    source.write_bytes(b"z" * (MIB + 800))
    remote = FakeGitHub()
    app = engine(tmp_path, remote)
    def interrupt_preparation(phase, done, total, detail):
        if phase == "hashing" and done > 0:
            app.request_pause()

    with pytest.raises(JobPaused, match="Preparation paused"):
        app.upload(source, "owner/repo", "dev", chunk_mib=1,
                   callback=interrupt_preparation)
    paused = app.store.list_sessions()
    assert len(paused) == 1
    assert paused[0]["preparing"] is True
    assert paused[0]["status"] == "paused"
    assert paused[0]["source"] == str(source.resolve())
    assert remote.commit_count == 0
    resumed = engine(tmp_path, remote).upload(source, "owner/repo", "dev", chunk_mib=1)
    assert resumed["status"] == "complete"
    assert any(s["status"] == "superseded" for s in app.store.list_sessions())


def test_restore_pause_and_resume_after_reboot_without_target_overwrite(tmp_path: Path) -> None:
    from strapman.engine import JobPaused
    from strapman.core import MIB
    source = tmp_path / "large-restore.bin"
    source.write_bytes(b"c" * (MIB + 500))
    remote = FakeGitHub()
    remote_upload = engine(tmp_path, remote).upload(source, "owner/repo", "main", chunk_mib=1)
    target = tmp_path / "restored-output.bin"
    first = engine(tmp_path, remote)
    def pause_while_downloading(phase, done, total, detail):
        if phase == "downloading" and done:
            first.request_pause()

    with pytest.raises(JobPaused, match="Restore paused"):
        first.restore("owner/repo", "main", remote_upload["manifest_path"], target,
                      workers=1, callback=pause_while_downloading)
    assert not target.exists()
    checkpoints = [s for s in first.store.list_sessions() if s.get("job_kind") == "restore"]
    assert len(checkpoints) == 1
    assert checkpoints[0]["status"] == "paused"
    assert checkpoints[0]["destination"] == str(target.resolve())
    result = engine(tmp_path, remote).restore("owner/repo", "main",
                                              remote_upload["manifest_path"], target, workers=1)
    assert result == target
    assert target.read_bytes() == source.read_bytes()
    assert first.store.session(checkpoints[0]["checkpoint_id"])["status"] == "complete"
    with pytest.raises(FileExistsError):
        engine(tmp_path, remote).restore("owner/repo", "main",
                                          remote_upload["manifest_path"], target)
    assert target.read_bytes() == source.read_bytes()


def test_abort_remains_cancelled_not_paused(tmp_path: Path) -> None:
    source = tmp_path / "cancel.bin"
    source.write_bytes(b"x" * (1024 * 1024 + 9))
    app = engine(tmp_path, FakeGitHub())
    def cancel_on_publish(phase, done, total, detail):
        if phase == "committing":
            app.abort()
    with pytest.raises(InterruptedError, match="cancelled"):
        app.upload(source, "owner/repo", "main", chunk_mib=1,
                   workers=1, callback=cancel_on_publish)
    assert app.store.list_sessions()[0]["status"] == "cancelled"


def test_bounded_network_tasks_do_not_prefetch_entire_manifest():
    from concurrent.futures import ThreadPoolExecutor
    from strapman.engine import _bounded_results
    seen = []
    def many_parts():
        for index in range(200):
            seen.append(index)
            yield index
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = _bounded_results(pool, lambda index: index, many_parts(), workers=2)
        first = next(results)
        assert first in range(200)
        assert len(seen) <= 5  # Two workers × two queued; one replacement.
        assert sorted([first, *results]) == list(range(200))
    with ThreadPoolExecutor(max_workers=3) as pool:
        assert sorted(_bounded_results(pool, lambda i: i * i, range(100), workers=3)) == [i * i for i in range(100)]
