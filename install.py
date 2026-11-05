#!/usr/bin/env python3
"""Cross-platform local bootstrap with reusable dependencies and a disk gate.

A healthy Python environment is reused across extracted Strapman updates.
The default new environment lives in the user's app-data/cache directory,
not alongside the downloaded ZIP. Existing local and sibling installations
can be reused without copying or reinstalling their dependencies.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

BASE = Path(__file__).resolve().parent
MIN_FREE_BYTES = 1536 * 1024 * 1024


def check_platform() -> None:
    if sys.version_info < (3, 10):
        raise RuntimeError('Strapman requires Python 3.10 or newer')
    if not (sys.platform.startswith('linux') or sys.platform == 'win32'):
        raise RuntimeError('This release supports Windows and Linux')


def _user_runtime() -> Path:
    override = os.environ.get('STRAPMAN_VENV', '').strip()
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == 'win32':
        root = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    else:
        root = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache')
    return root / 'Strapman' / 'python-runtime' / f'py{sys.version_info.major}{sys.version_info.minor}'


def venv_executable(root: Path | None = None) -> Path:
    directory = root if root is not None else _user_runtime()
    return directory / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')


def _disk_root(directory: Path) -> Path:
    probe = directory.expanduser().resolve()
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    return probe


def check_disk(directory: Path | None = None) -> tuple[int, int]:
    """Run before installing dependencies, using the destination filesystem."""
    available = shutil.disk_usage(_disk_root(directory or _user_runtime())).free
    if available < MIN_FREE_BYTES:
        raise RuntimeError(
            f'Not enough free storage for a safe dependency install: '
            f'{available / 1024**3:.2f} GiB available; '
            f'at least {MIN_FREE_BYTES / 1024**3:.2f} GiB required'
        )
    return available, MIN_FREE_BYTES


# Run with the candidate interpreter. The environment must provide compatible
# versions, not merely import similarly named modules.
_DEPENDENCY_PROBE = r'''from importlib.metadata import version
from pathlib import Path
from pip._vendor.packaging.requirements import Requirement
import PySide6, requests, keyring
from PySide6.QtWidgets import QApplication
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
for line in Path(__import__('sys').argv[1]).read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if line and not line.startswith('#'):
        spec = Requirement(line)
        if version(spec.name) not in spec.specifier:
            raise RuntimeError('Dependency version not satisfied: ' + spec.name)
'''


def dependencies_present(python: Path) -> bool:
    if not python.is_file():
        return False
    try:
        probe = subprocess.run([str(python), '-c', _DEPENDENCY_PROBE,
                                str(BASE / 'requirements.txt')], check=False,
                               timeout=35, capture_output=True)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def _legacy_environments():
    """Locate previous unpacked releases without scanning outside nearby folders.

    The normal ZIP layout has two nested directories (e.g. Downloads/repo/repo).
    Visit at most 40 nearby edition-labelled folders; no recursive walk.
    Nothing is moved, modified, deleted, or copied from an older installation.
    """
    yield BASE / '.venv'
    seen = {str(BASE.resolve())}
    count = 0
    for parent in (BASE.parent, BASE.parent.parent):
        try:
            siblings = sorted(parent.iterdir(), key=lambda p: p.name.casefold())
        except (PermissionError, OSError):
            continue
        for sibling in siblings:
            if count >= 40:
                return
            if sibling.is_symlink() or not sibling.is_dir() or 'strapman' not in sibling.name.casefold():
                continue
            count += 1
            for source in (sibling, sibling / 'strapman-dev-main'):
                if not (source / 'install.py').is_file():
                    continue
                resolved = str(source.resolve())
                if resolved not in seen:
                    seen.add(resolved)
                    yield source / '.venv'


def setup() -> Path:
    check_platform()
    shared = _user_runtime()
    candidates = [shared]
    # Explicit STRAPMAN_VENV is authoritative. Do not search other locations
    # when the user explicitly selected an environment.
    if not os.environ.get('STRAPMAN_VENV', '').strip():
        candidates.extend(_legacy_environments())
    for candidate in candidates:
        python = venv_executable(candidate)
        if dependencies_present(python):
            print(f'Reusing an existing Strapman Python environment: {candidate}', flush=True)
            return python

    available, required = check_disk(shared)
    print(f'Space check passed: {available / 1024**3:.2f} GiB free '
          f'(required {required / 1024**3:.2f} GiB).', flush=True)
    python = venv_executable(shared)
    if not python.is_file():
        print('Creating a reusable per-user Strapman Python environment...', flush=True)
        shared.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(shared)
    print('Installing only missing or incompatible dependencies...', flush=True)
    subprocess.run([str(python), '-m', 'pip', 'install',
                    '--disable-pip-version-check', '-r', str(BASE / 'requirements.txt')],
                   cwd=BASE, check=True)
    if not dependencies_present(python):
        raise RuntimeError('Dependencies were installed, but their compatibility check failed')
    return python


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-space', action='store_true',
                        help='Report available space; make no changes or downloads')
    parser.add_argument('--no-launch', action='store_true',
                        help='Install dependencies but do not launch the GUI')
    parser.add_argument('--edition', choices=('lite', 'bootlegger'), default='lite',
                        help='Edition to launch; dependencies are shared, settings are separate')
    args = parser.parse_args()
    try:
        check_platform()
        if args.check_space:
            available, minimum = check_disk()
            print(f'Space available: {available:,} bytes; minimum: {minimum:,} bytes')
            return 0
        python = setup()
        if not args.no_launch:
            environment = dict(os.environ, STRAPMAN_EDITION=args.edition)
            return subprocess.call([str(python), '-m', 'strapman'], cwd=BASE, env=environment)
        print('Strapman dependency setup complete.', flush=True)
        return 0
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'Strapman setup failed: {exc}', file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
