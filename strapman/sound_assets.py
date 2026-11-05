"""Validate and reconstruct multipart, owner-supplied Bootlegger voice clips.

No network access, source deletion, file overwrite, conversion or audio
transcoding is used. New recordings may also be delivered as checksum-pinned Git-tracked .part blobs.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile


class AudioAssetError(RuntimeError):
    """Audio is unavailable or an owner-provided part did not validate."""


PARTS = {
    "codebase_updated.mp3": {
        "sha256": "9bcc3101de57b113aa88e359ec8a748ace381de6a27463e9b22c103b32af6cf2",
        "parts": (
            ("000", "88cb55cda25619fd1d42fa767483798b1b52c8c43a7c804b759d0ee3aa612d93"),
            ("001", "081ec389bdce0b67bfa0ca3120f0b4e368ca86eb5647fee435d197a8faabdbdd"),
            ("002", "0e66b3bb11793c4480acc849b628fd62a1187732d597f04cbe6c60da6a4018f5"),
        ),
    },
    "readme_updated.mp3": {
        "sha256": "83ddaf10f1eb087bf433bd2b10dc3917423fb5d71360bba888aab16b5586e11e",
        "parts": (
            ("000", "b82da81348580004c22fe3ac7508530eda4f98dfea6a9b2409a7ab27879caaf0"),
            ("001", "0595fdc89c2ea0096dd7e1c55097f2817bcd1bda79902c890a216effbadc9005"),
        ),
    },
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
    Only explicitly checksum-pinned audio clips are eligible for rebuild.
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
