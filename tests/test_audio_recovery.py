"""Verify that Bootlegger's offline multipart rebuild refuses corrupted data."""
from pathlib import Path
import hashlib

import pytest

from strapman.sound_assets import PARTS, AudioAssetError, ensure_audio_asset


def test_new_recordings_have_exact_pinned_sha256_and_part_counts():
    for name, full_digest, count in (
        ("readme_updated.mp3", "83ddaf10f1eb087bf433bd2b10dc3917423fb5d71360bba888aab16b5586e11e", 2),
        ("codebase_updated.mp3", "9bcc3101de57b113aa88e359ec8a748ace381de6a27463e9b22c103b32af6cf2", 3),
    ):
        assert PARTS[name]["sha256"] == full_digest
        assert len(PARTS[name]["parts"]) == count
        assert all(len(suffix) == 3 and len(digest) == 64
                   for suffix, digest in PARTS[name]["parts"])


def test_reconstruct_missing_mp3_checks_every_part_and_never_overwrites(monkeypatch, tmp_path):
    source = b"ID3owner-supplied-voice" * 6
    first, second = source[:37], source[37:]
    name = "isolated_rebuild_test.mp3"
    monkeypatch.setitem(PARTS, name, {
        "sha256": hashlib.sha256(source).hexdigest(),
        "parts": (("000", hashlib.sha256(first).hexdigest()),
                  ("001", hashlib.sha256(second).hexdigest())),
    })
    folder = tmp_path / ".parts"
    folder.mkdir()
    (folder / (name + ".000.part")).write_bytes(first)
    (folder / (name + ".001.part")).write_bytes(second)
    target = tmp_path / name
    assert ensure_audio_asset(target, verify_only=True) == "parts verified"
    assert not target.exists()
    assert ensure_audio_asset(target) == "reconstructed"
    assert target.read_bytes() == source
    assert ensure_audio_asset(target) == "verified"
    target.write_bytes(b"ID3altered")
    with pytest.raises(AudioAssetError, match="differs"):
        ensure_audio_asset(target)
    assert target.read_bytes() == b"ID3altered"


def test_corrupted_part_fails_without_publishing_output(monkeypatch, tmp_path):
    name = "isolated_corruption_test.mp3"
    raw = b"ID3good"
    monkeypatch.setitem(PARTS, name, {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "parts": (("000", hashlib.sha256(raw).hexdigest()),),
    })
    folder = tmp_path / ".parts"
    folder.mkdir()
    (folder / (name + ".000.part")).write_bytes(b"ID3bad")
    output = tmp_path / name
    with pytest.raises(AudioAssetError, match="checksum failed"):
        ensure_audio_asset(output)
    assert not output.exists()
