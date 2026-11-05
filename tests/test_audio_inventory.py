"""The full checkout must include byte-exact Bootlegger sounds in both sources."""
from __future__ import annotations

from pathlib import Path
import hashlib

from strapman.editions import BOOTLEGGER, LITE, SOUND_EVENTS, audio_path, repository_write_sound_event
from tools.verify_audio_assets import EXPECTED, git_blob_id, verify_audio


def test_every_sound_event_is_mapped_to_a_unique_mp3():
    assert len(SOUND_EVENTS) == 16
    assert len(EXPECTED) == len(SOUND_EVENTS)
    assert set(EXPECTED) == set(SOUND_EVENTS.values())
    for event, filename in SOUND_EVENTS.items():
        assert filename.endswith(".mp3")
        assert audio_path(Path("/repo"), event, LITE) is None
        assert audio_path(Path("/repo"), event, BOOTLEGGER) == (
            Path("/repo") / "bootlegger/assets/sounds" / filename)


def test_audio_auditor_detects_missing_modified_and_exact_unchanged_copies(tmp_path):
    clip = b"ID3" + b"verified-shipped-voice"
    sha = hashlib.sha1(f"blob {len(clip)}\0".encode("ascii") + clip).hexdigest()
    for sub in ("assets/sounds", "bootlegger/assets/sounds"):
        folder = tmp_path / sub
        folder.mkdir(parents=True)
        (folder / "voice.mp3").write_bytes(clip)
        assert git_blob_id(folder / "voice.mp3") == (len(clip), sha)
    expected = {"voice.mp3": (len(clip), sha)}
    assert verify_audio(tmp_path, expected=expected)["success"] is True
    target = tmp_path / "bootlegger/assets/sounds/voice.mp3"
    target.write_bytes(b"ID3" + b"corrupted-shipped-voice")
    assert "Audio bytes differ" in " ".join(verify_audio(tmp_path, expected=expected)["problems"])
    target.unlink()
    assert "Missing voice clip" in " ".join(verify_audio(tmp_path, expected=expected)["problems"])


def test_repository_write_cues_are_distinct_and_case_insensitive():
    assert repository_write_sound_event("README.md") == "readme_updated"
    assert repository_write_sound_event("docs/README.MD") == "readme_updated"
    assert repository_write_sound_event("src/core.py") == "codebase_updated"
    assert repository_write_sound_event("configs/config.json") == "codebase_updated"
