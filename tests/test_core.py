from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from strapman.core import (MIB, Store, assemble_local, chunk_source, parse_repository,
                           validate_manifest, verify_local_chunks)


def test_repository_parsing() -> None:
    assert parse_repository('example/repo') == 'example/repo'
    assert parse_repository('https://github.com/example/repo.git') == 'example/repo'
    assert parse_repository('git@github.com:example/repo.git') == 'example/repo'
    for invalid in ('https://fake-github.com/example/repo', '../../secrets',
                    'example/repo/other', 'file://example/repo', 'example//repo'):
        with pytest.raises(ValueError):
            parse_repository(invalid)


def test_chunk_split_verify_reassemble(tmp_path: Path) -> None:
    payload = bytes(range(256)) * 9000
    original = tmp_path / 'original.zip'
    original.write_bytes(payload)
    store = Store(tmp_path / 'application')
    manifest, folder = chunk_source(original, 1, store)
    assert len(manifest['chunks']) == 3
    assert manifest['size'] == len(payload)
    assert manifest['sha256'] == hashlib.sha256(payload).hexdigest()
    verify_local_chunks(folder, manifest)
    reconstructed = tmp_path / 'reconstructed.zip'
    assert assemble_local(folder, manifest, reconstructed) == reconstructed
    assert reconstructed.read_bytes() == payload
    with pytest.raises(FileExistsError):
        assemble_local(folder, manifest, reconstructed)
    # A second split uses the verified cached chunks.
    assert chunk_source(original, 1, store)[0] == manifest


def test_chunk_tampering_fails(tmp_path: Path) -> None:
    source = tmp_path / 'image.bin'
    source.write_bytes(b'a' * (MIB + 11))
    manifest, folder = chunk_source(source, 1, Store(tmp_path / 'state'))
    (folder / 'chunks' / 'part-000001').write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        verify_local_chunks(folder, manifest)
    with pytest.raises(ValueError):
        assemble_local(folder, manifest, tmp_path / 'output.bin')
    assert not (tmp_path / 'output.bin').exists()


def test_malformed_manifest_rejected() -> None:
    manifest = {'format': 'strapman-chunks-v1', 'schema': 1, 'name': 'ok.bin',
                'size': 1, 'sha256': 'a' * 64, 'chunk_mib': 1,
                'chunks': [{'index': 0, 'filename': '../private', 'size': 1,
                            'sha256': 'b' * 64}]}
    with pytest.raises(ValueError):
        validate_manifest(manifest)
    manifest['chunks'][0]['filename'] = 'part-000000'
    validate_manifest(manifest)
    manifest['chunks'][0]['size'] = 2
    with pytest.raises(ValueError):
        validate_manifest(manifest)


def test_restore_race_does_not_replace_new_destination(tmp_path: Path) -> None:
    source = tmp_path / "archive.bin"
    source.write_bytes(b"verified content" * 4000)
    manifest, folder = chunk_source(source, 1, Store(tmp_path / "state"))
    target = tmp_path / "recovered.bin"
    def racer(phase: str, done: int, total: int, detail: str) -> None:
        if phase == "assembling" and not target.exists():
            target.write_bytes(b"other process's file")
    with pytest.raises(FileExistsError):
        assemble_local(folder, manifest, target, callback=racer)
    assert target.read_bytes() == b"other process's file"
    assert not list(tmp_path.glob(".strapman-restore-*.incomplete"))


def test_job_history_preserves_ids_and_last_update(tmp_path: Path) -> None:
    app = Store(tmp_path)
    session = {"upload_id": "content-hash", "checkpoint_id": "destination-key",
               "status": "uploading"}
    app.save("destination-key", session)
    row = app.list_sessions()[0]
    assert row["upload_id"] == "content-hash"
    assert row["checkpoint_id"] == "destination-key"
    assert row["updated"].endswith("Z")


def test_last_block_pause_never_publishes_reconstructed_destination(tmp_path: Path) -> None:
    import threading
    source = tmp_path / "backup.dat"
    source.write_bytes(b"pausable restore content" * 800)
    manifest, root = chunk_source(source, 1, Store(tmp_path / "local"))
    dest = tmp_path / "destination.dat"
    pause = threading.Event()
    def request_at_final_block(phase, done, total, detail):
        if phase == "assembling" and done == total:
            pause.set()
    with pytest.raises(InterruptedError, match="paused or cancelled"):
        assemble_local(root, manifest, dest, callback=request_at_final_block, stop=pause)
    assert not dest.exists()
    assert not list(tmp_path.glob(".strapman-restore-*.incomplete"))
