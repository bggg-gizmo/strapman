#!/usr/bin/env python3
"""Start sound-free Strapman in an existing Python runtime without installing Qt.

This launcher itself uses only the Python standard library. Its child command
uses the existing Strapman dependencies but does not run pip or an installer.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from install import _legacy_environments, _user_runtime, venv_executable  # noqa: E402


def candidates():
    """Honor a selected venv; otherwise prefer the prior healthy app runtime."""
    selected = bool(os.environ.get("STRAPMAN_VENV", "").strip())
    yield venv_executable(_user_runtime())
    if not selected:
        for directory in _legacy_environments():
            yield venv_executable(directory)
        yield Path(sys.executable)


def supports_headless(python: Path) -> bool:
    if not python.is_file():
        return False
    try:
        # Import test only; never installs packages or loads Qt.
        result = subprocess.run([str(python), "-c", "import requests"],
                                capture_output=True, timeout=12, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def find_python() -> Path | None:
    seen: set[str] = set()
    for candidate in candidates():
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        if supports_headless(candidate):
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    python = find_python()
    if python is None:
        print("Headless Strapman needs Python requests. No environment was changed or downloaded.\n"
              "To use an existing desktop install, launch Strapman once from its usual .cmd/.sh.\n"
              "Otherwise install only the small 'requests' package into your selected Python; "
              "PySide6, sounds and desktop dependencies are not required for headless commands.",
              file=sys.stderr)
        return 1
    return subprocess.call([str(python), "-m", "strapman.headless", *(argv or [])], cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
