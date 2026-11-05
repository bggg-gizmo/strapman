"""Bootlegger's Windows-native MP3 player.

The Windows MCI mpegvideo driver can play MP3 files without Qt's FFmpeg audio
output or a third-party runtime. No external process or network access is used.
The caller may try another backend if MCI is unavailable.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys


class AudioPlaybackError(RuntimeError):
    """A local audio backend could not start the requested cue."""


class WindowsMp3Player:
    """Use winmm/MCI with one unique alias; never touch the upload engine."""

    def __init__(self, api=None) -> None:
        if api is None:
            if sys.platform != "win32":
                raise AudioPlaybackError("Windows-native MP3 playback is unavailable on this OS")
            try:
                api = ctypes.WinDLL("winmm")
            except (OSError, AttributeError) as exc:
                raise AudioPlaybackError("Windows multimedia audio is unavailable") from exc
        self._api = api
        self._alias = f"bggbootlegger_{os.getpid()}_{id(self):x}"
        self._open = False
        self._filename = ""

    def _error(self, code: int) -> str:
        try:
            buffer = ctypes.create_unicode_buffer(512)
            if self._api.mciGetErrorStringW(code, buffer, len(buffer)):
                return buffer.value
        except (AttributeError, OSError, ValueError):
            pass
        return f"Windows multimedia error {code}"

    def _send(self, command: str, *, result: bool = False) -> str:
        buffer = ctypes.create_unicode_buffer(128) if result else None
        try:
            code = self._api.mciSendStringW(command, buffer, len(buffer) if buffer is not None else 0, None)
        except (AttributeError, OSError) as exc:
            raise AudioPlaybackError("Windows multimedia command could not execute") from exc
        if code:
            raise AudioPlaybackError(self._error(code))
        return buffer.value if buffer is not None else ""

    def stop(self) -> None:
        if self._open:
            try:
                self._send(f"close {self._alias}")
            finally:
                self._open = False
                self._filename = ""

    def play(self, path: Path) -> None:
        path = Path(path)
        if not path.is_file():
            raise AudioPlaybackError(f"MP3 missing: {path.name}")
        if path.suffix.lower() != ".mp3":
            raise AudioPlaybackError("Unsupported audio asset format")
        # Windows cannot contain double quotes in a real path. Defense in depth:
        # avoid passing synthetic quote injection into an MCI command string.
        if '"' in str(path):
            raise AudioPlaybackError("Invalid MP3 file path")
        try:
            self.stop()
        except AudioPlaybackError:
            self._open = False
        self._send(f'open "{path.resolve()}" type mpegvideo alias {self._alias}')
        self._open = True
        self._filename = path.name
        try:
            # The volume command is optional on some drivers. Do not reject
            # working MP3 playback just because the device ignores this command.
            try:
                self._send(f"setaudio {self._alias} volume to 1000")
            except AudioPlaybackError:
                pass
            self._send(f"play {self._alias} from 0")
        except AudioPlaybackError:
            self.stop()
            raise

    def playback_state(self) -> str:
        if not self._open:
            return "closed"
        try:
            return self._send(f"status {self._alias} mode", result=True).lower()
        except AudioPlaybackError:
            return "unknown"

    def close(self) -> None:
        self.stop()
