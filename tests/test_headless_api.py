"""Headless commands share actual engine method names without requiring Qt."""
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from strapman.headless import HeadlessController, _cli_parser, _progress_html, safe_session
from strapman.workbench import check_syntax


def test_rebuild_github_parser_is_first_class():
    args = _cli_parser().parse_args([
        "rebuild-github", "--repo", "alice/repo", "--branch", "main",
        "--manifest", "strapman-uploads/id/manifest.json", "--destination", "out.bin"])
    assert args.operation == "rebuild-github"
    assert args.destination == "out.bin"


def test_local_dashboard_encodes_untrusted_session_names():
    report = {"application": "headless-strapman", "edition": "lite",
              "captured_at": "now", "run": {"done": 10, "total": 20},
              "sessions": [{"name": "<script>alert(1)</script>", "repo": "alice/repo"}]}
    page = _progress_html(report)
    assert "&lt;script&gt;" in page
    assert "<script>alert(1)</script>" not in page


def test_headless_session_redacts_private_paths():
    row = {"source": "/workspace/private/data.bin", "destination": "/workspace/private/out.bin",
           "checkpoint_id": "id", "token": "secret-token", "published": ["one"]}
    result = safe_session(row)
    assert "token" not in result
    assert "/workspace/private" not in json.dumps(result)
    assert result["source_name"] == "data.bin"


def test_headless_status_reads_during_heartbeat_updates(tmp_path):
    from strapman.core import Journal, Store

    controller = HeadlessController(Store(tmp_path / "checkpoints"), Journal(tmp_path / "logs"))
    controller._save_run({"run_id": "a" * 32, "state": "running", "done": 0})

    def read_many():
        for _ in range(120):
            assert controller._status()["run_id"] == "a" * 32

    def write_many():
        for done in range(120):
            controller._save_run({"run_id": "a" * 32, "state": "running", "done": done})

    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(read_many) for _ in range(3)] + [pool.submit(write_many)]
        for job in jobs:
            job.result()
    assert controller._status()["done"] == 119


def test_headless_offline_rebuild_does_not_request_github_login(tmp_path, monkeypatch):
    from strapman.core import Journal, Store, chunk_source
    from strapman import headless
    source = tmp_path / "sample.bin"
    source.write_bytes(bytes(range(256)) * 1200)
    store = Store(tmp_path / "checkpoints")
    manifest, cache = chunk_source(source, 1, store)
    # No GitHub connection or token is available in offline rebuild mode.
    def forbidden_github():
        raise AssertionError("Offline rebuild must never request GitHub credentials")
    monkeypatch.setattr(headless, "GitHub", forbidden_github)
    controller = HeadlessController(store, Journal(tmp_path / "logs"))
    destination = tmp_path / "reconstructed.bin"
    result = controller.rebuild_local(str(cache / "manifest.json"), str(cache), str(destination))
    assert result["state"] == "complete"
    assert destination.read_bytes() == source.read_bytes()
    sessions = store.list_sessions()
    assert any(s["job_kind"] == "restore-local" and s["status"] == "complete" for s in sessions)


def test_headless_offline_rebuild_checkpoint_survives_pause(tmp_path, monkeypatch):
    from strapman.core import Journal, Store, chunk_source
    from strapman.engine import Engine, JobPaused
    from strapman import headless
    source = tmp_path / "original.bin"
    source.write_bytes(b"abcde" * 80000)
    store = Store(tmp_path / "checkpoints")
    manifest, cache = chunk_source(source, 1, store)
    original = Engine(None, store, Journal(tmp_path / "logs"))
    output = tmp_path / "after-restart.bin"
    def pause_when_assembling(phase, done, total, detail):
        if phase == "assembling" and done:
            original.request_pause()
    with __import__("pytest").raises(JobPaused):
        original.rebuild_local(cache / "manifest.json", cache, output, callback=pause_when_assembling)
    paused = [s for s in store.list_sessions() if s.get("job_kind") == "restore-local"]
    assert len(paused) == 1
    assert paused[0]["status"] == "paused"
    assert not output.exists()
    monkeypatch.setattr(headless, "GitHub", lambda: (_ for _ in ()).throw(AssertionError("Offline cannot use GitHub")))
    restarted = HeadlessController(store, Journal(tmp_path / "logs"))
    result = restarted.resume(paused[0]["checkpoint_id"])
    assert result["state"] == "complete"
    assert output.read_bytes() == source.read_bytes()
