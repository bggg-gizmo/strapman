"""Hard-kill interruption regression tests: no cooperative cleanup is assumed.

These intentionally kill *child* Python processes only. Never terminate the
pytest runner, an unrelated process, or a real Strapman worker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from strapman.core import Journal, Store, chunk_source
from strapman.engine import Engine
from strapman.headless import HeadlessController
from test_engine import FakeGitHub


ROOT = Path(__file__).resolve().parents[1]


def _child(script: str, *args: str, stdin=None) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, "-c", script, *args], cwd=ROOT,
                          env=env, capture_output=True, text=True,
                          stdin=stdin, timeout=30)


def test_hard_exit_during_first_hash_has_durable_resume_record(tmp_path):
    source = tmp_path / "input.bin"
    content = b"source-data" * 12000
    source.write_bytes(content)
    state = tmp_path / "state"
    script = '''
import os, sys
from pathlib import Path
from strapman.core import Store, Journal
from strapman.engine import Engine
def crash(phase, done, total, detail):
    if phase == 'hashing' and done:
        os._exit(42)
Engine(None, Store(Path(sys.argv[2])), Journal(Path(sys.argv[3]))).upload(
    Path(sys.argv[1]), 'example/disposable', 'main', callback=crash)
'''
    child = _child(script, str(source), str(state), str(tmp_path / "logs"))
    assert child.returncode == 42, child.stderr
    store = Store(state)
    active = store.list_sessions()
    assert len(active) == 1
    checkpoint = active[0]["checkpoint_id"]
    assert active[0]["status"] == "preparing"
    assert store.job_is_running("upload") is False
    assert store.recover_interrupted_jobs() == [checkpoint]
    assert store.session(checkpoint)["status"] == "interrupted"
    assert store.recover_interrupted_jobs() == []
    remote = FakeGitHub()
    resumed = Engine(remote, Store(state), Journal(tmp_path / "logs")).upload(
        source, "example/disposable", "main")
    assert resumed["status"] == "complete"
    assert source.read_bytes() == content
    assert store.session(checkpoint)["status"] == "superseded"
    assert remote.commit_count >= 1


def test_changed_original_after_hard_exit_does_not_resume_different_bytes(tmp_path):
    source = tmp_path / "source.txt"
    source.write_bytes(b"a" * 8192)
    state = tmp_path / "state"
    script = '''
import os, sys
from pathlib import Path
from strapman.core import Store, Journal
from strapman.engine import Engine
def crash(phase, done, total, detail):
    if phase == 'hashing' and done: os._exit(39)
Engine(None, Store(Path(sys.argv[2])), Journal(Path(sys.argv[3]))).upload(
    Path(sys.argv[1]), 'example/disposable', 'main', callback=crash)
'''
    assert _child(script, str(source), str(state), str(tmp_path / "logs")).returncode == 39
    store = Store(state)
    assert len(store.recover_interrupted_jobs()) == 1
    original_mtime = source.stat().st_mtime_ns
    source.write_bytes(b"b" * 8192)
    os.utime(source, ns=(original_mtime + 10**9, original_mtime + 10**9))
    remote = FakeGitHub()
    with pytest.raises(ValueError, match="Original source changed"):
        Engine(remote, store, Journal(tmp_path / "logs")).upload(source, "example/disposable", "main")
    assert remote.commit_count == 0


def test_live_worker_lock_prevents_false_interrupted_status(tmp_path):
    store = Store(tmp_path / "store")
    store.save("active-record", {"job_kind": "upload", "status": "uploading",
                                 "checkpoint_id": "active-record", "name": "example.bin"})
    script = '''
import sys
from pathlib import Path
from strapman.core import Store
with Store(Path(sys.argv[1])).job_lock('upload'):
    print('LOCK_ACQUIRED', flush=True)
    sys.stdin.readline()
'''
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    worker = subprocess.Popen([sys.executable, "-u", "-c", script, str(tmp_path / "store")],
                              cwd=ROOT, env=env, stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert worker.stdout.readline().strip() == "LOCK_ACQUIRED"
        assert store.job_is_running("upload") is True
        assert store.recover_interrupted_jobs() == []
        assert store.session("active-record")["status"] == "uploading"
    finally:
        worker.stdin.write("stop\n")
        worker.stdin.flush()
        worker.communicate(timeout=10)
    assert store.job_is_running("upload") is False
    assert store.recover_interrupted_jobs() == ["active-record"]
    assert store.session("active-record")["status"] == "interrupted"


def test_hard_exit_during_local_build_preserves_existing_output_and_restores(tmp_path):
    source = tmp_path / "original.bin"
    original = b"rebuild-data" * 20000
    source.write_bytes(original)
    store = Store(tmp_path / "store")
    manifest, cache = chunk_source(source, 1, store)
    target = tmp_path / "reconstructed.bin"
    script = '''
import os, sys
from pathlib import Path
from strapman.core import Store, Journal
from strapman.engine import Engine
def crash(phase, done, total, detail):
    if phase == 'assembling' and done:
        os._exit(55)
Engine(None, Store(Path(sys.argv[4])), Journal(Path(sys.argv[5]))).rebuild_local(
    Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), callback=crash)
'''
    result = _child(script, str(cache / "manifest.json"), str(cache), str(target),
                    str(tmp_path / "store"), str(tmp_path / "logs"))
    assert result.returncode == 55, result.stderr
    assert not target.exists()
    checkpoints = [s for s in store.list_sessions() if s.get("job_kind") == "restore-local"]
    assert len(checkpoints) == 1
    assert checkpoints[0]["status"] == "assembling"
    recovered = store.recover_interrupted_jobs()
    assert checkpoints[0]["checkpoint_id"] in recovered
    controller = HeadlessController(store, Journal(tmp_path / "logs"))
    resumed = controller.resume(checkpoints[0]["checkpoint_id"])
    assert resumed["state"] == "complete"
    assert target.read_bytes() == original
    assert source.read_bytes() == original


def test_headless_uses_os_lock_not_recent_stale_heartbeat(tmp_path):
    store = Store(tmp_path / "store")
    controller = HeadlessController(store, Journal(tmp_path / "logs"))
    controller._save_run({"run_id": "0" * 32, "state": "running", "phase": "uploading",
                          "command": "upload", "done": 10, "total": 100})
    assert controller.view()["run"]["state"] == "interrupted"
    with store.job_lock("headless"):
        assert controller.view()["run"]["state"] == "running"
        with pytest.raises(Exception, match="already running"):
            controller._execute("probe", "checking", lambda engine, callback: "ok", needs_github=False)
    assert controller._execute("probe", "checking", lambda engine, callback: "ok",
                               needs_github=False)["state"] == "complete"
    assert controller.view()["run"]["state"] == "complete"
