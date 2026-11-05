"""Pure logic for unplug reminders, voice defaults and integrity-safe MP3 rebuild."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from strapman.core import DEFAULT_SETTINGS
from strapman.editions import BOOTLEGGER, LITE, SOUND_EVENTS, PowerReminder, audio_path
from strapman.sound_assets import AudioAssetError, PARTS, ensure_audio_asset


def test_voice_on_by_default_and_lite_never_requires_voice_files():
    assert DEFAULT_SETTINGS["voice_enabled"] is True
    assert DEFAULT_SETTINGS["sound_enabled"] is True
    for event in SOUND_EVENTS:
        assert audio_path(Path("/never-exists"), event, LITE) is None
        assert audio_path(Path("/checkout"), event, BOOTLEGGER).name == SOUND_EVENTS[event]
    assert set(SOUND_EVENTS) >= {"upload_resuming", "work_paused", "verification_started",
                                 "repository_private", "repository_refreshed",
                                 "vulnerability_alerts_enabled", "automated_security_fixes_enabled"}


def test_unplugged_is_announced_each_minute_and_restoration_once():
    power = PowerReminder(initial=True, interval_seconds=60)
    assert power.poll(True, 0) is None
    assert power.poll(False, 10) == "power_unplugged"
    assert power.poll(False, 69.9) is None
    assert power.poll(False, 70) == "power_unplugged"
    assert power.poll(False, 129.9) is None
    assert power.poll(False, 130) == "power_unplugged"
    assert power.poll(None, 150) is None
    assert power.poll(True, 160) == "power_restored"
    assert power.poll(True, 161) is None
    assert power.poll(False, 170) == "power_unplugged"


def test_initial_unplugged_and_unknown_status_handling():
    p = PowerReminder(initial=False)
    assert p.poll(None, 0) is None
    assert p.poll(False, 1) == "power_unplugged"
    assert p.poll(False, 60) is None
    assert p.poll(False, 61) == "power_unplugged"
    assert PowerReminder(initial=None).poll(True, 5) is None
    with pytest.raises(ValueError):
        PowerReminder(interval_seconds=0)


def test_multipart_asset_reconstructs_and_refuses_to_replace_modified_asset(tmp_path, monkeypatch):
    sound = tmp_path / "spoken.mp3"
    parts = sound.parent / ".parts"
    parts.mkdir()
    chunks = [b"ID3header", b"voice bytes\x00\xff"]
    for index, data in enumerate(chunks):
        (parts / f"spoken.mp3.{index:03d}.part").write_bytes(data)
    monkeypatch.setitem(PARTS, sound.name, {
        "sha256": hashlib.sha256(b"".join(chunks)).hexdigest(),
        "parts": tuple((f"{i:03d}", hashlib.sha256(data).hexdigest()) for i, data in enumerate(chunks))
    })
    assert ensure_audio_asset(sound, verify_only=True) == "parts verified"
    assert not sound.exists()
    assert ensure_audio_asset(sound) == "reconstructed"
    assert sound.read_bytes() == b"".join(chunks)
    assert ensure_audio_asset(sound) == "verified"
    sound.write_bytes(b"tampered")
    with pytest.raises(AudioAssetError, match="differs"):
        ensure_audio_asset(sound)
    assert sound.read_bytes() == b"tampered"


def test_multipart_refuses_corrupt_parts(tmp_path, monkeypatch):
    sound = tmp_path / "spoken.mp3"
    parts = tmp_path / ".parts"
    parts.mkdir()
    (parts / "spoken.mp3.000.part").write_bytes(b"bad")
    monkeypatch.setitem(PARTS, sound.name, {"sha256": "0" * 64, "parts": (("000", "1" * 64),)})
    with pytest.raises(AudioAssetError, match="checksum"):
        ensure_audio_asset(sound)
    assert not sound.exists()
