#!/usr/bin/env python3
"""Verify every shipped Bootlegger voice asset against the source Git blobs.

This tool is read-only. It checks all configured event MP3s in the
private source and Bootlegger's package without starting playback or changing
files. It never requires GitHub, Qt, tokens, audio hardware, or installs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from strapman.editions import SOUND_EVENTS

# The original 14 Git blob IDs were verified against the development repository.
# The two newly supplied recordings were verified byte-for-byte locally; their
# GitHub publication is not confirmed until the private bootstrap publisher
# commits the finished files and checks the remote tree/readback.
# Each tuple is (file size, Git blob object ID). No token or device path is stored.
EXPECTED = {
    "application_error.mp3": (142986, "0cb6b85020a68058a2696561551ef3cf16fb1d1c"),
    "application_exit.mp3": (81546, "1d2ac498baea28f010befbb9d4511ed4c2464eae"),
    "application_ready.mp3": (89069, "a54349ca2d525e62f4ba43acf0c462f2ac1b6a6b"),
    "codebase_updated.mp3": (110385, "3f11d2da4a4d6c335ffb6f6323b93db5390bc32a"),
    "automated_security_fixes_enabled.mp3": (97219, "c8be7dea8ea3641b77766641a736579f66095ab7"),
    "first_run_github_setup.mp3": (168063, "f928e473cb860c627dd692d60407d6c02cce2164"),
    "power_restored.mp3": (133582, "99c72d2820f9e3c676a60c1757ffd7cf4cc5d537"),
    "power_unplugged.mp3": (70261, "3320a270a781e6b4344120b4f07f5c2af2fc68a8"),
    "repository_private.mp3": (79665, "cd0957a1a716775d8ee6723cf830b021538306b7"),
    "repository_refreshed.mp3": (72142, "005a0c722146a2b8ead0ade4eaf385fb6d743b1b"),
    "readme_updated.mp3": (89069, "d184a53d5b14e9c41211b6ae23e7b998ac81151d"),
    "task_complete.mp3": (92830, "91167f566d5745d6c38655618830589b7d96fb43"),
    "upload_resuming.mp3": (81546, "19cbedf071ddebe5d39f8549937b17086775ac88"),
    "verification_started.mp3": (74022, "a1d270cbf09a80c7e29d68faa0a32f1419e1c433"),
    "vulnerability_alerts_enabled.mp3": (90950, "6c487470ccbe283501e59f4a82738d08dff4b71e"),
    "work_paused.mp3": (60230, "db5c78b88d372a4504e6a40cb144ba7391e46cc1"),
}


def git_blob_id(path: Path) -> tuple[int, str]:
    size = path.stat().st_size
    digest = hashlib.sha1(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return size, digest.hexdigest()


def verify_audio(root: Path, *, expected: dict | None = None) -> dict:
    root = Path(root)
    inventory = dict(EXPECTED if expected is None else expected)
    issues = []
    if expected is None and set(inventory) != set(SOUND_EVENTS.values()):
        issues.append("The MP3 catalogue and SOUND_EVENTS mapping differ")
    examined = 0
    for folder in (root / "assets/sounds", root / "bootlegger/assets/sounds"):
        if not folder.is_dir():
            issues.append(f"Missing audio directory: {folder.relative_to(root)}")
            continue
        extra = {file.name for file in folder.glob("*.mp3")} - set(inventory)
        if extra:
            issues.append(f"Unmapped MP3 files in {folder.relative_to(root)}: {', '.join(sorted(extra))}")
        for filename, (size, sha) in sorted(inventory.items()):
            path = folder / filename
            if not path.is_file():
                issues.append(f"Missing voice clip: {path.relative_to(root)}")
                continue
            actual = git_blob_id(path)
            examined += 1
            if actual != (size, sha):
                issues.append(f"Audio bytes differ from source: {path.relative_to(root)}")
    return {"success": not issues, "event_count": len(SOUND_EVENTS),
            "expected_clip_copies": 2 * len(inventory), "checked_clip_copies": examined,
            "problems": issues}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="Root of an extracted complete Strapman checkout")
    parser.add_argument("--json", action="store_true", help="Machine-readable verification result")
    args = parser.parse_args(argv)
    result = verify_audio(args.root)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"AUDIO {'PASS' if result['success'] else 'FAIL'}: "
              f"{result['checked_clip_copies']}/{result['expected_clip_copies']} "
              f"MP3 copies verified; {len(SOUND_EVENTS)} mapped events")
        for error in result["problems"]:
            print("  " + error, file=sys.stderr)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
