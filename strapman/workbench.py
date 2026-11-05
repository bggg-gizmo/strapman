"""Local text/code workbench: inspect, validate, diff and save with backups.

Does not execute project code. It never changes GitHub, job checkpoints or
original uploaded sources unless the user explicitly saves an opened file.
"""
from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
import tempfile
try:
    import tomllib  # Python 3.11+
except ImportError:
    tomllib = None  # Python 3.10: syntax validation is explicitly unavailable
import uuid

MAX_TEXT_BYTES = 8 * 1024 * 1024


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_text(path: Path) -> tuple[str, bytes]:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError(f"Workbench text files must be at most {MAX_TEXT_BYTES:,} bytes")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("This looks like a binary file; use Restore instead of the text workbench")
    try:
        return raw.decode("utf-8-sig"), raw
    except UnicodeDecodeError as exc:
        raise ValueError("Workbench requires UTF-8 text; source was not changed") from exc


def check_syntax(text: str, filename: str) -> dict:
    """Validate recognized formats without executing any source code."""
    suffix = Path(filename).suffix.lower()
    kind = {".py": "python", ".json": "json", ".toml": "toml"}.get(suffix)
    if not kind:
        return {"supported": False, "valid": None, "kind": "plain-text",
                "message": "No built-in syntax validator for this file type; file was not executed"}
    try:
        if kind == "python":
            compile(text, filename, "exec", dont_inherit=True)
        elif kind == "json":
            json.loads(text)
        else:
            if tomllib is None:
                return {"supported": False, "valid": None, "kind": "toml",
                        "message": "TOML syntax validation requires Python 3.11+; no code was executed"}
            tomllib.loads(text)
    except (SyntaxError, ValueError, TypeError) as exc:
        return {"supported": True, "valid": False, "kind": kind,
                "line": getattr(exc, "lineno", None),
                "column": getattr(exc, "offset", getattr(exc, "colno", None)),
                "message": str(exc)}
    return {"supported": True, "valid": True, "kind": kind,
            "message": f"Valid {kind} syntax; no code was executed"}


class TextWorkbench:
    def __init__(self):
        self.path: Path | None = None
        self.original = ""
        self.disk_sha256 = ""

    def open(self, path: Path) -> str:
        candidate = Path(path).expanduser().resolve(strict=True)
        text, raw = _read_text(candidate)
        self.path = candidate
        self.original = text
        self.disk_sha256 = _digest(raw)
        return text

    def diff(self, edited: str) -> str:
        if self.path is None:
            raise ValueError("Open a local file first")
        return "".join(difflib.unified_diff(
            self.original.splitlines(keepends=True), edited.splitlines(keepends=True),
            fromfile=str(self.path) + " (loaded)", tofile=str(self.path) + " (edited)"))

    def save(self, edited: str) -> Path:
        """Explicit save, refusing stale files and backing up the old bytes."""
        if self.path is None:
            raise ValueError("Open a local file first")
        target = self.path
        _, raw = _read_text(target)
        if _digest(raw) != self.disk_sha256:
            raise FileExistsError("File changed on disk after loading; reload and reconcile before saving")
        replacement = edited.encode("utf-8")
        if len(replacement) > MAX_TEXT_BYTES:
            raise ValueError("Edited text exceeds the supported 8 MiB workbench limit")
        if edited == self.original:
            return target
        backup = target.with_name(target.name + ".strapman-" + uuid.uuid4().hex + ".bak")
        # Keep the original bytes in an exclusive backup before replacing them.
        with backup.open("xb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        fd, scratch = tempfile.mkstemp(prefix=".strapman-edit-", dir=target.parent)
        try:
            with os.fdopen(fd, "wb") as out:
                out.write(replacement)
                out.flush()
                os.fsync(out.fileno())
            if _digest(target.read_bytes()) != self.disk_sha256:
                raise FileExistsError("File changed during saving; original and backup retained")
            os.replace(scratch, target)
        finally:
            if os.path.exists(scratch):
                os.unlink(scratch)
        self.original = edited
        self.disk_sha256 = _digest(replacement)
        return target

    def save_as(self, edited: str, destination: Path) -> Path:
        """Create a new file exclusively, never overwrite an existing path."""
        path = Path(destination).expanduser().resolve()
        data = edited.encode("utf-8")
        if len(data) > MAX_TEXT_BYTES:
            raise ValueError("Edited text exceeds the supported 8 MiB workbench limit")
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        self.path, self.original, self.disk_sha256 = path, edited, _digest(data)
        return path


class RemoteTextWorkbench:
    """Immutable remote scope + optimistic GitHub SHA for explicit reviewed commits."""

    def __init__(self):
        self.scope: tuple[str, str, str, str] | None = None
        self.original = ""
        self.sha = ""

    def bind(self, login: str, repo: str, branch: str, path: str,
             text: str, sha: str = "") -> None:
        from .github import validate_repository_file_path
        path = validate_repository_file_path(path)
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("Remote editor has an 8 MiB text-file limit")
        if sha and (len(sha) != 40 or not all(ch in "0123456789abcdef" for ch in sha)):
            raise ValueError("Invalid GitHub version SHA")
        if not all((login, repo, branch)):
            raise ValueError("The account, repository and branch must be selected")
        self.scope = (login, repo, branch, path)
        self.original = text
        self.sha = sha

    def dirty(self, edited: str) -> bool:
        return self.scope is not None and edited != self.original

    def diff(self, edited: str) -> str:
        if self.scope is None:
            raise ValueError("Load or create a GitHub file before reviewing changes")
        path = self.scope[3]
        return "".join(difflib.unified_diff(
            self.original.splitlines(keepends=True), edited.splitlines(keepends=True),
            fromfile=f"{path} (GitHub)", tofile=f"{path} (proposed)"))

    def prepare_commit(self, login: str, repo: str, branch: str, path: str,
                       edited: str) -> str:
        from .github import validate_repository_file_path
        if self.scope != (login, repo, branch, validate_repository_file_path(path)):
            raise ValueError("GitHub account, repository, branch or file changed. Reload before saving")
        if not self.dirty(edited):
            raise ValueError("There are no changes to commit")
        if len(edited.encode("utf-8")) > MAX_TEXT_BYTES:
            raise ValueError("Remote editor has an 8 MiB text-file limit")
        return self.sha


def run_local_tests(folder: Path, *, timeout_seconds: int = 120,
                    framework: str = "unittest") -> dict:
    """Run explicitly authorized local unittest or pytest suites, never remote code.

    Auto prefers pytest only if it is already installed in this Python
    environment. Nothing is installed implicitly or run without UI consent.
    """
    root = Path(folder).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    if not 1 <= timeout_seconds <= 600:
        raise ValueError("Timeout must be between one and 600 seconds")
    if framework not in {"auto", "unittest", "pytest"}:
        raise ValueError("Test framework must be auto, unittest or pytest")
    pytest_available = importlib.util.find_spec("pytest") is not None
    if framework == "auto":
        framework = "pytest" if pytest_available else "unittest"
    if framework == "pytest" and not pytest_available:
        raise RuntimeError("pytest is not installed in the active Python environment; select unittest")
    if framework == "pytest":
        command = [sys.executable, "-m", "pytest", "-q", str(root)]
    else:
        command = [sys.executable, "-m", "unittest", "discover", "-s", str(root),
                   "-p", "test_*.py", "-v"]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True,
                                text=True, errors="replace", timeout=timeout_seconds,
                                check=False)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Local {framework} test run exceeded {timeout_seconds} seconds") from exc
    output = result.stdout + result.stderr
    if framework == "pytest":
        counts = re.findall(r"(\d+) (passed|failed|error|errors|skipped|xfailed|xpassed)\b", output)
        tests = sum(int(count) for count, _ in counts)
    else:
        found = re.search(r"Ran (\d+) tests?", output)
        tests = int(found.group(1)) if found else 0
    if not tests:
        raise ValueError(f"No {framework} tests were discovered; no test pass is claimed")
    return {"exit_code": result.returncode, "framework": framework,
            "tests": tests, "passed": result.returncode == 0, "output": output}
