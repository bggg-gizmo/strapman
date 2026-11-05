"""Validate and reconstruct multipart, owner-supplied Bootlegger voice clips.

No network access, source deletion, file overwrite, conversion or audio
transcoding is used. Two large MP3s were delivered as Git-tracked .part blobs.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile


class AudioAssetError(RuntimeError):
    """Audio is unavailable or an owner-provided part did not validate."""


PARTS = {
    "vulnerability_alerts_enabled.mp3": {
        "sha256": "da4487ff8ebfc1d918110d8abcfa3bb07e62e32af64f0dd86f59cffdbc3a5826",
        "parts": (("000", "78ad1827d9e1d054454e10f4233d6c53c09524c66cc16fce3f680726da821972"),
                  ("001", "31d1611c689a10ff554eb8349ac1da0f8e593aeb0b6d0120a26ccd72e818fbc0")),
    },
    "automated_security_fixes_enabled.mp3": {
        "sha256": "a28b4e30e5dd324cb72169e43eb7d2b8f7d52554b6f1e8594af6110ca77ec4c3",
        "parts": (("000", "1c96aaef21fe17fae833be75afd36c1e53b9bc2854b795f4d99b3433c0ee8d3f"),
                  ("001", "fd8d101798a5af002bdccf15a96bb288a87a42dc1177e799e3e71ab8516e4d5a")),
    },
}


def ensure_audio_asset(destination: Path, *, verify_only: bool = False) -> str:
    """Verify or construct a supported multipart MP3 at its committed location.

    Existing targets are *never* replaced. Missing sources fail visibly.
    This is intentionally limited to the two known multipart audio clips.
    """
    target = Path(destination)
    spec = PARTS.get(target.name)
    if spec is None:
        return "not multipart"
    if target.is_file():
        if hashlib.sha256(target.read_bytes()).hexdigest() != spec["sha256"]:
            raise AudioAssetError(f"Audio asset differs from verified source: {target.name}")
        return "verified"
    if target.exists():
        raise AudioAssetError(f"Audio target is not an ordinary file: {target.name}")
    result = bytearray()
    for suffix, expected in spec["parts"]:
        part = target.parent / ".parts" / (target.name + "." + suffix + ".part")
        try:
            raw = part.read_bytes()
        except OSError as exc:
            raise AudioAssetError(f"Missing or unreadable audio component: {part.name}") from exc
        if hashlib.sha256(raw).hexdigest() != expected:
            raise AudioAssetError(f"Audio component checksum failed: {part.name}")
        result.extend(raw)
    if hashlib.sha256(result).hexdigest() != spec["sha256"]:
        raise AudioAssetError(f"Reconstructed MP3 checksum failed: {target.name}")
    if verify_only:
        return "parts verified"
    fd, temporary = tempfile.mkstemp(prefix=".strapman-audio-", suffix=".tmp", dir=target.parent)
    tmp = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(result)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            if os.name == "nt":
                os.rename(tmp, target)  # Windows refuses an existing destination.
            else:
                os.link(tmp, target)  # POSIX exclusive/non-replacing publication.
        except FileExistsError:
            # Another instance may have successfully built the same verified file.
            if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == spec["sha256"]:
                return "verified"
            raise AudioAssetError(f"Audio destination changed during reconstruction: {target.name}")
    except OSError as exc:
        raise AudioAssetError(f"Cannot save reconstructed MP3: {target.name}: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)
    return "reconstructed"
