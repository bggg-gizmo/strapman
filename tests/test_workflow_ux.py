"""v0.5.2 release regressions for automatic workflows and UI semantics."""
from __future__ import annotations

from pathlib import Path

from strapman.core import Settings
from tests.test_engine import FakeGitHub, engine


def test_existing_settings_upgrade_to_automated_build_once(tmp_path):
    root = tmp_path / 'settings'
    root.mkdir()
    (root / 'settings.json').write_text('{"reconstruct_after_upload": false, "sound_enabled": true}')
    settings = Settings(root)
    assert settings.get('reconstruct_after_upload') is True
    settings.set('reconstruct_after_upload', False)
    assert Settings(root).get('reconstruct_after_upload') is False


def test_new_install_reconstruct_default_is_on(tmp_path):
    assert Settings(tmp_path / 'fresh').get('reconstruct_after_upload') is True


def test_automatic_workflow_verifies_rebuilt_file(tmp_path):
    original = tmp_path / 'model-data.bin'
    original.write_bytes(bytes(range(256)) * 4500)
    git = FakeGitHub()
    worker = engine(tmp_path, git)
    phases = []
    result = worker.upload(original, 'example/project', 'main', chunk_mib=1, workers=3,
                           reconstruct=True,
                           callback=lambda phase, *_: phases.append(phase))
    assert result['status'] == 'complete'
    assert result['workflow_status'] == 'complete'
    assert result['reconstruction_status'] == 'complete'
    assert Path(result['reconstruction_path']).read_bytes() == original.read_bytes()
    assert 'downloading' in phases and 'assembling' in phases
    assert phases[-1] == 'complete'
    assert result['final_commit']


def test_failed_post_upload_build_keeps_commit_and_does_not_claim_completion(tmp_path):
    original = tmp_path / 'asset.bin'
    original.write_bytes(b'test' * 4096)
    git = FakeGitHub()
    worker = engine(tmp_path, git)
    real_restore = worker.restore
    def fail(*args, **kwargs):
        raise OSError('Simulated rebuild media error')
    worker.restore = fail
    result = worker.upload(original, 'example/project', 'main', reconstruct=True)
    assert result['status'] == 'rebuild_failed'
    assert result['workflow_status'] == 'rebuild_failed'
    assert result['final_commit']
    assert result['reconstruction_status'] == 'failed'
    committed = git.commit_count
    worker.restore = real_restore
    resumed = worker.upload(original, 'example/project', 'main', reconstruct=True)
    assert resumed['status'] == 'complete'
    assert resumed['reconstruction_status'] == 'complete'
    assert git.commit_count == committed


def test_existing_upload_only_checkpoint_can_be_built_without_new_commit(tmp_path):
    original = tmp_path / 'archive.zip'
    original.write_bytes(b'archives!' * 2000)
    git = FakeGitHub()
    worker = engine(tmp_path, git)
    published = worker.upload(original, 'example/project', 'main', reconstruct=False)
    assert published['status'] == 'complete'
    assert not published.get('reconstruction_path')
    before = git.commit_count
    recovered = worker.upload(original, 'example/project', 'main', reconstruct=True)
    assert recovered['status'] == 'complete'
    assert recovered['reconstruction_status'] == 'complete'
    assert Path(recovered['reconstruction_path']).read_bytes() == original.read_bytes()
    assert git.commit_count == before


def test_top_workflow_is_not_duplicate_of_sidebar():
    source = (Path(__file__).resolve().parents[1] / 'strapman' / 'ui.py').read_text()
    assert 'self._workflow_sections' in source
    assert 'def _jump_workflow' in source
    assert 'button.clicked.connect(lambda checked=False, n=index: self._jump_workflow(n))' in source
    assert 'button.clicked.connect(lambda checked=False, page=index: self._navigate(page))' in source
    assert 'brand_header.addLayout(brand_top)' in source
    assert 'brand_header.addWidget(self.brand_title)' in source
    assert '"Upload Station"' in source and '"Repository Desk"' in source
    assert '"Browse & edit code"' in source


def test_pause_after_remote_commit_resumes_rebuild_without_duplicate_commit(tmp_path):
    original = tmp_path / 'dataset.bin'
    original.write_bytes(b'byte-exact-reconstruction' * 900)
    git = FakeGitHub()
    worker = engine(tmp_path, git)

    def pause_after_manifest(phase, done, total, detail):
        if phase == 'committing' and 'Committed manifest' in detail:
            worker.request_pause()

    first = worker.upload(original, 'example/project', 'main', reconstruct=True,
                          callback=pause_after_manifest)
    assert first['status'] == 'rebuild_paused'
    assert first['final_commit']
    assert first['reconstruction_status'] == 'paused'
    committed = git.commit_count
    continued = worker.upload(original, 'example/project', 'main', reconstruct=True)
    assert continued['status'] == 'complete'
    assert continued['reconstruction_status'] == 'complete'
    assert git.commit_count == committed
