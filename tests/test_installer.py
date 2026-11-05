"""Installer reuse and storage behavior, all without installing any packages."""
from pathlib import Path
import subprocess
import sys

import pytest

import install


def test_default_runtime_is_independent_of_zip_extraction(monkeypatch, tmp_path):
    monkeypatch.delenv('STRAPMAN_VENV', raising=False)
    monkeypatch.setenv('XDG_CACHE_HOME', str(tmp_path))
    monkeypatch.setattr(install.sys, 'platform', 'linux')
    target = install._user_runtime()
    assert target == tmp_path / 'Strapman' / 'python-runtime' / f'py{sys.version_info.major}{sys.version_info.minor}'
    assert '.venv' not in target.parts


def test_explicit_existing_runtime_is_preferred(monkeypatch, tmp_path):
    target = tmp_path / 'already-installed'
    monkeypatch.setenv('STRAPMAN_VENV', str(target))
    monkeypatch.setattr(install, 'dependencies_present', lambda py: py == install.venv_executable(target))
    monkeypatch.setattr(install, 'check_disk', lambda *args: pytest.fail('no install should occur'))
    monkeypatch.setattr(install.subprocess, 'run', lambda *a, **k: pytest.fail('no pip should run'))
    assert install.setup() == install.venv_executable(target)


def test_reuses_local_legacy_without_install(monkeypatch, tmp_path):
    base = tmp_path / 'strapman-dev-main' / 'strapman-dev-main'
    base.mkdir(parents=True)
    (base / 'install.py').touch()
    monkeypatch.setattr(install, 'BASE', base)
    monkeypatch.delenv('STRAPMAN_VENV', raising=False)
    monkeypatch.setattr(install, '_user_runtime', lambda: tmp_path / 'shared-env')
    expected = install.venv_executable(base / '.venv')
    monkeypatch.setattr(install, 'dependencies_present', lambda py: py == expected)
    monkeypatch.setattr(install, 'check_disk', lambda *args: pytest.fail('no install should occur'))
    assert install.setup() == expected


def test_reuses_previous_download_zip_venv(monkeypatch, tmp_path):
    old = tmp_path / 'strapman-dev-main' / 'strapman-dev-main'
    new = tmp_path / 'strapman-dev-main (1)' / 'strapman-dev-main'
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    (old / 'install.py').touch()
    (new / 'install.py').touch()
    monkeypatch.setattr(install, 'BASE', new)
    monkeypatch.delenv('STRAPMAN_VENV', raising=False)
    monkeypatch.setattr(install, '_user_runtime', lambda: tmp_path / 'stable-env')
    expected = install.venv_executable(old / '.venv')
    monkeypatch.setattr(install, 'dependencies_present', lambda py: py == expected)
    monkeypatch.setattr(install, 'check_disk', lambda *args: pytest.fail('no install should occur'))
    monkeypatch.setattr(install.subprocess, 'run', lambda *a, **k: pytest.fail('no pip should run'))
    assert install.setup() == expected


def test_new_runtime_uses_disk_gate_before_creating(monkeypatch, tmp_path):
    monkeypatch.delenv('STRAPMAN_VENV', raising=False)
    monkeypatch.setattr(install, 'BASE', tmp_path)
    monkeypatch.setattr(install, '_user_runtime', lambda: tmp_path / 'stable')
    monkeypatch.setattr(install, 'dependencies_present', lambda _: False)
    monkeypatch.setattr(install, 'check_disk', lambda *args: (_ for _ in ()).throw(RuntimeError('disk too small')))
    monkeypatch.setattr(install.venv, 'EnvBuilder', lambda **k: pytest.fail('cannot create before disk gate'))
    with pytest.raises(RuntimeError, match='disk too small'):
        install.setup()


def test_dependencies_probe_does_not_accept_missing_python(tmp_path):
    assert install.dependencies_present(tmp_path / 'nothing' / 'python') is False
