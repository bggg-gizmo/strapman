#!/usr/bin/env python3
"""Restore multipart, byte-exact Strapman MP3 assets from Git-tracked parts.

Run: python tools/rebuild_strapman_audio.py [--verify-only]
This only touches the two named audio assets in the main and Bootlegger Pro
folders. It never deletes source parts, overwrites existing files, or connects
with GitHub. It does not enable audio playback or any security settings.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOUND_DIRS = (ROOT / "assets/sounds", ROOT / "bootlegger/assets/sounds")
ASSETS = {
    "vulnerability_alerts_enabled.mp3": {
        "sha256": "da4487ff8ebfc1d918110d8abcfa3bb07e62e32af64f0dd86f59cffdbc3a5826",
        "parts": (
            ("000", "78ad1827d9e1d054454e10f4233d6c53c09524c66cc16fce3f680726da821972"),
            ("001", "31d1611c689a10ff554eb8349ac1da0f8e593aeb0b6d0120a26ccd72e818fbc0"),
        ),
    },
    "automated_security_fixes_enabled.mp3": {
        "sha256": "a28b4e30e5dd324cb72169e43eb7d2b8f7d52554b6f1e8594af6110ca77ec4c3",
        "parts": (
            ("000", "1c96aaef21fe17fae833be75afd36c1e53b9bc2854b795f4d99b3433c0ee8d3f"),
            ("001", "fd8d101798a5af002bdccf15a96bb288a87a42dc1177e799e3e71ab8516e4d5a"),
        ),
    },
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def restore_asset(folder: Path, name: str, entry: dict, verify_only: bool) -> str:
    assembled = bytearray()
    for suffix, expected_sha in entry["parts"]:
        part = folder / ".parts" / (name + "." + suffix + ".part")
        data = part.read_bytes()
        if sha256(data) != expected_sha:
            raise RuntimeError(f"Part integrity check failed: {part}")
        assembled.extend(data)
    result = bytes(assembled)
    if sha256(result) != entry["sha256"]:
        raise RuntimeError(f"Complete audio integrity check failed: {folder / name}")

    target = folder / name
    if target.exists():
        if not target.is_file() or sha256(target.read_bytes()) != entry["sha256"]:
            raise RuntimeError(f"Existing destination is different; refusing overwrite: {target}")
        return "verified"
    if verify_only:
        return "parts verified; MP3 not yet reconstructed"

    fd, temp_name = tempfile.mkstemp(prefix=".strapman-audio-", suffix=".tmp", dir=str(folder))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(result)
            out.flush()
            os.fsync(out.fileno())
        # Atomically publish without replacing an existing file.
        if os.name == "nt":
            os.rename(temp, target)  # Windows refuses an existing target.
        else:
            os.link(temp, target)  # POSIX exclusive publication.
        return "reconstructed"
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Check the tracked parts without writing MP3s")
    options = parser.parse_args()
    try:
        for folder in SOUND_DIRS:
            for name, entry in ASSETS.items():
                status = restore_asset(folder, name, entry, options.verify_only)
                print(f"{folder.relative_to(ROOT) / name}: {status}")
        return 0
    except (OSError, RuntimeError) as exc:
        print(f"Audio bootstrap failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
