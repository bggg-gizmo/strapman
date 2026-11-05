"""Bootlegger MP3 playback tests without requiring Qt or a Windows machine."""
from pathlib import Path

import pytest

from strapman.audio import AudioPlaybackError, WindowsMp3Player


class FakeMci:
    def __init__(self, failures=None):
        self.commands = []
        self.failures = failures or {}

    def mciSendStringW(self, command, buffer, size, callback):
        self.commands.append(command)
        for starts, code in self.failures.items():
            if command.startswith(starts):
                return code
        if command.startswith("status ") and buffer is not None:
            buffer.value = "playing"
        return 0

    def mciGetErrorStringW(self, code, buffer, size):
        buffer.value = f"Audio driver error {code}"
        return 1


def test_native_windows_mp3_plays_actual_file_and_reuses_single_alias(tmp_path):
    sound = tmp_path / "notification.mp3"
    sound.write_bytes(b"ID3a-validity-check-is-separate")
    backend = FakeMci()
    player = WindowsMp3Player(api=backend)
    player.play(sound)
    assert backend.commands[0].startswith('open "')
    assert ' type mpegvideo alias bggbootlegger_' in backend.commands[0]
    assert any(c.startswith("play bggbootlegger_") for c in backend.commands)
    assert player.playback_state() == "playing"
    player.play(sound)
    assert sum(c.startswith("close ") for c in backend.commands) == 1
    player.close()
    assert sum(c.startswith("close ") for c in backend.commands) == 2
    assert player.playback_state() == "closed"


def test_native_audio_driver_error_is_visible_and_closes_resource(tmp_path):
    sound = tmp_path / "effect.mp3"
    sound.write_bytes(b"ID3")
    backend = FakeMci({"play ": 271})
    player = WindowsMp3Player(api=backend)
    with pytest.raises(AudioPlaybackError, match="Audio driver error 271"):
        player.play(sound)
    assert any(c.startswith("close ") for c in backend.commands)


def test_native_audio_missing_asset_does_not_call_driver(tmp_path):
    backend = FakeMci()
    player = WindowsMp3Player(api=backend)
    with pytest.raises(AudioPlaybackError, match="missing"):
        player.play(tmp_path / "not-there.mp3")
    assert backend.commands == []


def test_native_audio_rejects_non_mp3_and_mci_injection(tmp_path):
    backend = FakeMci()
    player = WindowsMp3Player(api=backend)
    wav = tmp_path / "effect.wav"
    wav.write_bytes(b"WAVE")
    with pytest.raises(AudioPlaybackError, match="Unsupported"):
        player.play(wav)
    assert backend.commands == []


def test_native_audio_open_failure_does_not_leave_open_alias(tmp_path):
    mp3 = tmp_path / "effect.mp3"
    mp3.write_bytes(b"ID3")
    backend = FakeMci({"open ": 263})
    player = WindowsMp3Player(api=backend)
    with pytest.raises(AudioPlaybackError, match="Audio driver error 263"):
        player.play(mp3)
    player.close()
    assert len(backend.commands) == 1


def test_lite_never_requests_mp3_assets():
    from strapman.editions import SOUND_EVENTS, audio_path
    for event in SOUND_EVENTS:
        assert audio_path(Path('/checkout'), event, 'lite') is None
