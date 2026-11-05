#!/usr/bin/env python3
"""Fail-closed, read-only prepublication inspection of Strapman source and Git history.

This is a sensitive-content heuristic, not proof that all private details are absent.
Run with --history in a real Git checkout before creating the public repository.
No network connections, uploads, mutations, or hosted CI are performed.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SOURCE_EXTENSIONS = {".py", ".md", ".txt", ".svg", ".sh", ".cmd", ".ps1",
                     ".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".xml",
                     ".bat", ".properties", ".gitignore", ".gitattributes"}
PRIVATE_SUFFIXES = {".pem", ".p12", ".pfx", ".key", ".sqlite3", ".db", ".env",
                    ".token", ".secret", ".log", ".jsonl", ".zip", ".7z"}
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache",
             ".ruff_cache", "build", "dist", "htmlcov"}
MAX_INSPECT_BYTES = 32 * 1024 * 1024
REDACTIONS = (
    ("GitHub token", re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
    ("Cloud access key", re.compile(rb"\bAKIA[A-Z0-9]{16}\b")),
    ("Private key", re.compile(rb"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("Home-folder path", re.compile(rb"(?i:[A-Z]:\\" + b"Users" + rb"\\[^\\\s\"']+|/" + b"Users" + rb"/[^/\s\"']+|/" + b"home" + rb"/[^/\s\"']+)")),
    ("Real-looking email address", re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)
ALLOWED_EMAIL_SUFFIXES = (b"@users.noreply.github.com", b"@noreply.github.com")


def validate_path(path: str) -> list[str]:
    normalized = path.replace("\\", "/")
    name = Path(normalized).name
    issues: list[str] = []
    parts = normalized.split("/")
    if name == ".env" or name.startswith(".env.") or Path(name).suffix.lower() in PRIVATE_SUFFIXES:
        issues.append("Private or archive file must not be published")
    if len(parts) > 2 and parts[0:2] == [".github", "workflows"]:
        issues.append("Unexpected GitHub Actions workflow; review paid-workflow policy")
    if any(part.startswith(".") and part.endswith(".swp") for part in parts):
        issues.append("Editor swap file")
    return issues


def validate_bytes(data: bytes) -> list[str]:
    findings: list[str] = []
    for name, pattern in REDACTIONS:
        matches = pattern.findall(data)
        if name == "Real-looking email address":
            # git@github.com:<owner>/<repo>.git is a legitimate SSH Git URL,
            # not an email address. Other domains and mailbox forms are audited.
            matches = [value for value in matches if not value.lower().endswith(ALLOWED_EMAIL_SUFFIXES)
                       and not (value.lower() == b"git@github.com"
                                and b"git@github.com:" in data)]
        if matches:
            findings.append(name)
    return findings


def validate_file(path: str, data: bytes) -> list[str]:
    issues = validate_path(path)
    if len(data) > MAX_INSPECT_BYTES:
        issues.append("File exceeds inspection size limit")
    elif Path(path).suffix.lower() in SOURCE_EXTENSIONS or Path(path).name in {".gitignore", ".gitattributes"}:
        issues.extend(validate_bytes(data))
    return issues


def source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and not (set(path.relative_to(root).parts) & SKIP_DIRS):
            yield path.relative_to(root).as_posix(), path.read_bytes()


def history_files(root: Path):
    if not (root / ".git").exists():
        raise RuntimeError("Full Git history audit needs a Git checkout; source archives have no history")
    listed = subprocess.run(["git", "-C", str(root), "rev-list", "--objects", "--all"],
                            capture_output=True, check=True).stdout
    for record in listed.splitlines():
        oid, _, name = record.partition(b" ")
        if not re.fullmatch(rb"[a-f0-9]{40,64}", oid):
            raise RuntimeError("Unexpected Git object ID format")
        kind = subprocess.run(["git", "-C", str(root), "cat-file", "-t", oid.decode()],
                              capture_output=True, check=True).stdout.strip()
        if kind != b"blob":
            continue
        rel = name.decode("utf-8", errors="replace") if name else f"<unmapped object {oid.decode()[:12]}>"
        size = int(subprocess.run(["git", "-C", str(root), "cat-file", "-s", oid.decode()],
                                  capture_output=True, check=True).stdout)
        if size > MAX_INSPECT_BYTES:
            yield rel, b"", ["Historical object exceeds inspection size limit"]
            continue
        data = subprocess.run(["git", "-C", str(root), "cat-file", "blob", oid.decode()],
                              capture_output=True, check=True).stdout
        yield rel, data, []


def audit(root: Path, inspect_history: bool) -> tuple[int, list[str]]:
    issues: list[str] = []
    examined = 0
    for rel, data in source_files(root):
        examined += 1
        for finding in validate_file(rel, data):
            issues.append(f"HEAD:{rel}: {finding}")
    if inspect_history:
        for rel, data, special in history_files(root):
            examined += 1
            for finding in special or validate_file(rel, data):
                issues.append(f"HISTORY:{rel}: {finding}")
        author = subprocess.run(["git", "-C", str(root), "log", "--all", "--format=%ae%n%ce"],
                                capture_output=True, check=True).stdout
        for address in sorted(set(author.splitlines())):
            if address and not address.lower().endswith(ALLOWED_EMAIL_SUFFIXES):
                issues.append("HISTORY: Commit author/committer email needs review")
    return examined, issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", action="store_true", help="Audit every reachable Git blob and commit emails")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        count, issues = audit(args.root.resolve(strict=True), args.history)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"PUBLIC_AUDIT_ERROR: {exc}", file=sys.stderr)
        return 2
    for issue in issues:
        print(f"REVIEW_REQUIRED: {issue}")
    if issues:
        print(f"PUBLIC_AUDIT_FAIL files_and_blobs={count} findings={len(issues)}")
        return 1
    print(f"PUBLIC_AUDIT_PASS files_and_blobs={count} history={'checked' if args.history else 'NOT_CHECKED'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
