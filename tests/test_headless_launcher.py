"""The headless launcher only selects existing dependencies; never runs pip."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("headless_launcher", ROOT / "headless" / "launch.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)


def test_prefers_existing_runtime_without_install(monkeypatch, tmp_path):
    first = tmp_path / "existing" / "python.exe"
    first.parent.mkdir()
    first.write_bytes(b"binary stub")
    second = tmp_path / "system" / "python.exe"
    second.parent.mkdir()
    second.write_bytes(b"binary stub")
    monkeypatch.setattr(launcher, "candidates", lambda: iter((first, second)))
    monkeypatch.setattr(launcher, "supports_headless", lambda p: p == first)
    assert launcher.find_python() == first


def test_unavailable_runtime_fails_without_subprocess_install(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(launcher, "candidates", lambda: iter((tmp_path / "missing.exe",)))
    monkeypatch.setattr(launcher, "supports_headless", lambda p: False)
    def forbidden(*args, **kwargs):
        raise AssertionError("Launcher must not install or bootstrap packages")
    monkeypatch.setattr(launcher.subprocess, "call", forbidden)
    assert launcher.main(["status"]) == 1
    assert "No environment was changed or downloaded" in capsys.readouterr().err
