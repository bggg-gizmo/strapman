"""GitHub REST client. Direct local-to-GitHub requests; no hosted workflows."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import random
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from .core import VERSION, parse_repository
from .auth import github_cli_token, git_credential_token

API = "https://api.github.com"
TIMEOUT = (15, 180)


def validate_repository_file_path(path: str, *, allow_root: bool = False) -> str:
    """Reject traversal, Git internals and ambiguous remote paths before API calls."""
    if not isinstance(path, str) or not path and not allow_root:
        raise ValueError("A GitHub repository file path is required")
    if path == "" and allow_root:
        return ""
    if (len(path) > 1024 or path.startswith("/") or "\\" in path
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)):
        raise ValueError("Invalid GitHub file path")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts) or parts[0].lower() == ".git":
        raise ValueError("Unsafe GitHub file path")
    return path


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"GitHub HTTP {status}: {message}")
        self.status = status


def cli_token(username: str = "") -> str:
    """Return the selected GitHub CLI account token, without storing it."""
    return github_cli_token(username)


def saved_token(username: str = "") -> str:
    try:
        import keyring
        if username:
            return keyring.get_password("Strapman", "github:" + username) or ""
        return keyring.get_password("Strapman", "github") or ""
    except Exception:
        return ""


def store_token(value: str, username: str = "") -> None:
    if not username:
        raise ValueError("Account name required before storing credentials")
    import keyring
    keyring.set_password("Strapman", "github:" + username, value)


def delete_token(username: str = "") -> None:
    if not username:
        raise ValueError("Choose an account before removing credentials")
    try:
        import keyring
        keyring.delete_password("Strapman", "github:" + username)
    except Exception:
        return


class GitHub:
    def __init__(self, token: str = ""):
        self.token = token or os.environ.get("STRAPMAN_GITHUB_TOKEN", "") or saved_token() or git_credential_token() or cli_token()
        self._local = threading.local()
        if not self.token:
            raise ValueError("No usable GitHub login found; connect with a device code, saved token, Git credential helper, or GitHub CLI")

    def _session(self) -> requests.Session:
        if not hasattr(self._local, "session"):
            session = requests.Session()
            session.headers.update({
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": f"Strapman/{VERSION} (desktop)",
            })
            self._local.session = session
        return self._local.session

    def request(self, method: str, path: str, *, data: Any = None,
                params: dict[str, Any] | None = None, expected: tuple[int, ...] = (200,)) -> Any:
        url = API + path
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                response = self._session().request(method, url, json=data, params=params, timeout=TIMEOUT)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt == 4:
                    raise GitHubError(0, "Network connection failed after retries") from exc
                time.sleep(min(16, (2 ** attempt) + random.uniform(0, 0.5)))
                continue
            if response.status_code in expected:
                if response.status_code == 204 or not response.content:
                    return None
                return response.json()
            status = response.status_code
            try:
                body = response.json()
                message = str(body.get("message", "Request rejected"))
            except (json.JSONDecodeError, ValueError):
                message = response.text[:200]
            retryable = status in (429, 500, 502, 503, 504) or (
                status == 403 and (response.headers.get("X-RateLimit-Remaining") == "0"
                                   or "rate limit" in message.lower()))
            if retryable and attempt < 4:
                delay = min(32, 2 ** attempt + random.uniform(0, 0.8))
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = min(120, max(delay, float(retry_after)))
                if response.headers.get("X-RateLimit-Remaining") == "0":
                    try:
                        delay = min(120, max(delay, int(response.headers["X-RateLimit-Reset"]) - time.time() + 1))
                    except (KeyError, ValueError):
                        pass
                time.sleep(delay)
                continue
            raise GitHubError(status, message)
        raise GitHubError(0, f"Network retry exhaustion: {type(last_error).__name__}")

    def account(self) -> dict:
        return self.request("GET", "/user")

    def repositories(self) -> list[dict]:
        repos: list[dict] = []
        for page in range(1, 21):
            batch = self.request("GET", "/user/repos", params={"per_page": 100, "page": page,
                                                                    "affiliation": "owner,collaborator,organization_member"})
            repos.extend(batch)
            if len(batch) < 100:
                break
        return sorted(repos, key=lambda x: x["full_name"].lower())

    def repo_info(self, repo: str) -> dict:
        return self.request("GET", f"/repos/{parse_repository(repo)}")

    def branches(self, repo: str) -> list[str]:
        repo = parse_repository(repo)
        rows = []
        for page in range(1, 11):
            chunk = self.request("GET", f"/repos/{repo}/branches", params={"per_page": 100, "page": page})
            rows.extend(row["name"] for row in chunk)
            if len(chunk) < 100:
                break
        return rows

    def create_repo(self, name: str, description: str = "", private: bool = True) -> dict:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) or name in {".", ".."}:
            raise ValueError("Repository name must contain 1–100 valid characters")
        return self.request("POST", "/user/repos", data={"name": name, "description": description,
                        "private": private, "auto_init": True}, expected=(201,))

    def create_branch(self, repo: str, name: str, base: str) -> str:
        repo = parse_repository(repo)
        if not name or name.startswith("/") or ".." in name or " " in name or "~" in name or "^" in name or ":" in name:
            raise ValueError("Invalid Git branch name")
        head = self.branch_head(repo, base)
        self.request("POST", f"/repos/{repo}/git/refs", data={"ref": f"refs/heads/{name}",
                                                                 "sha": head}, expected=(201,))
        return name

    def list_directory(self, repo: str, branch: str, directory: str = "") -> list[dict]:
        """Browse only the requested directory of the selected branch (read-only)."""
        repo = parse_repository(repo)
        directory = validate_repository_file_path(directory, allow_root=True)
        suffix = "/" + quote(directory, safe="/") if directory else ""
        result = self.request("GET", f"/repos/{repo}/contents{suffix}", params={"ref": branch})
        if not isinstance(result, list):
            raise NotADirectoryError(f"Not a directory: {directory or '/'}")
        if len(result) >= 1000:
            raise ValueError("GitHub folder listing reached the 1,000-entry API limit; narrow the path")
        entries = []
        for entry in result:
            kind = entry.get("type")
            path = entry.get("path")
            if kind in ("file", "dir") and isinstance(path, str):
                try:
                    path = validate_repository_file_path(path)
                except ValueError:
                    continue
                entries.append({"name": entry.get("name", path.rsplit("/", 1)[-1]),
                                "path": path, "type": kind,
                                "size": int(entry.get("size") or 0)})
        return sorted(entries, key=lambda row: (row["type"] != "dir", row["name"].casefold()))

    def read_text(self, repo: str, path: str, ref: str = "") -> tuple[str, str] | None:
        repo = parse_repository(repo)
        escaped = quote(validate_repository_file_path(path), safe="/")
        try:
            value = self.request("GET", f"/repos/{repo}/contents/{escaped}",
                                 params={"ref": ref} if ref else None)
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise
        if value.get("type") != "file":
            raise ValueError("GitHub path is not an ordinary text file")
        if value.get("encoding") == "base64":
            encoded = "".join(value["content"].split())
            raw = base64.b64decode(encoded, validate=True)
            if hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest() != value.get("sha"):
                raise ValueError("GitHub text content does not match its Git blob SHA")
            content = raw.decode("utf-8")
        elif value.get("encoding") in ("none", None) and re.fullmatch(r"[0-9a-f]{40}", value.get("sha", "")):
            # GitHub omits content for files above 1 MiB in its Contents API.
            # The Git Blob endpoint returns the exact referenced bytes.
            content = self.get_blob(repo, value["sha"]).decode("utf-8")
        else:
            raise ValueError("Unsupported GitHub text-file encoding")
        return content, value["sha"]

    def write_text(self, repo: str, branch: str, path: str, content: str,
                   message: str, sha: str = "") -> dict:
        repo = parse_repository(repo)
        path = validate_repository_file_path(path)
        body = {"branch": branch, "message": message,
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii")}
        if sha:
            body["sha"] = sha
        return self.request("PUT", f"/repos/{repo}/contents/{quote(path, safe='/')}",
                            data=body, expected=(200, 201))

    def set_private(self, repo: str, private: bool = True) -> dict:
        repo = parse_repository(repo)
        return self.request("PATCH", f"/repos/{repo}", data={"private": private})

    def enable_vulnerability_alerts(self, repo: str) -> None:
        repo = parse_repository(repo)
        self.request("PUT", f"/repos/{repo}/vulnerability-alerts", expected=(204,))

    def enable_automated_fixes(self, repo: str) -> None:
        repo = parse_repository(repo)
        self.request("PUT", f"/repos/{repo}/automated-security-fixes", expected=(204,))

    def branch_head(self, repo: str, branch: str) -> str:
        value = self.request("GET", f"/repos/{parse_repository(repo)}/git/ref/heads/{quote(branch, safe='/')}")
        return value["object"]["sha"]

    def commit_object(self, repo: str, sha: str) -> dict:
        return self.request("GET", f"/repos/{parse_repository(repo)}/git/commits/{sha}")

    def create_blob(self, repo: str, data: bytes) -> str:
        if len(data) > 16 * 1024 * 1024:
            raise ValueError("Chunk exceeds Strapman's 16 MiB Git blob limit")
        body = {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"}
        reply = self.request("POST", f"/repos/{parse_repository(repo)}/git/blobs", data=body, expected=(201,))
        expected_sha = hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
        actual_sha = reply.get("sha", "")
        if actual_sha != expected_sha:
            raise ValueError("GitHub returned a blob SHA that does not match the uploaded bytes")
        return actual_sha

    def get_blob(self, repo: str, sha: str) -> bytes:
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("Invalid requested Git blob SHA")
        reply = self.request("GET", f"/repos/{parse_repository(repo)}/git/blobs/{sha}")
        if reply.get("encoding") != "base64":
            raise ValueError("Unexpected Git blob encoding")
        encoded = "".join(reply["content"].split())
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != reply["size"]:
            raise ValueError("Received Git blob size does not match metadata")
        actual = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
        if actual != sha or reply.get("sha", sha) != sha:
            raise ValueError("Received Git blob content does not match the requested SHA")
        return raw

    def folder_blobs(self, repo: str, branch: str, folder: str) -> dict[str, str]:
        """Read Git-tracked blobs at one directory from a consistent branch snapshot.

        Walking non-recursive Git trees avoids one REST request per chunk and
        avoids mistaking orphan blobs for committed/uploaded data. Fail closed
        if GitHub reports a truncated tree rather than claiming full coverage.
        """
        repo = parse_repository(repo)
        parts = folder.split("/")
        if not parts or any(part in ("", ".", "..") for part in parts):
            raise ValueError("Invalid GitHub folder path")
        head = self.branch_head(repo, branch)
        tree_sha = self.commit_object(repo, head)["tree"]["sha"]
        for component in parts:
            listing = self.request("GET", f"/repos/{repo}/git/trees/{tree_sha}")
            if listing.get("truncated"):
                raise ValueError("GitHub tree listing was truncated; refusing an incomplete audit")
            entry = next((item for item in listing["tree"] if item["path"] == component), None)
            if entry is None:
                return {}
            if entry["type"] != "tree":
                raise FileExistsError(f"GitHub directory path is occupied by a file: {folder}")
            tree_sha = entry["sha"]
        listing = self.request("GET", f"/repos/{repo}/git/trees/{tree_sha}")
        if listing.get("truncated"):
            raise ValueError("GitHub chunk listing was truncated; refusing an incomplete audit")
        return {entry["path"]: entry["sha"] for entry in listing["tree"]
                if entry["type"] == "blob"}

    def list_strapman_manifests(self, repo: str, branch: str) -> list[str]:
        """Discover complete Strapman upload manifests attached to a branch.

        This is a read-only snapshot of the committed tree. An uploaded Git
        blob or an unfinished set of parts does not constitute a buildable
        upload. The manifest and parts are validated again when rebuilding.
        """
        repo = parse_repository(repo)
        head = self.branch_head(repo, branch)
        tree_sha = self.commit_object(repo, head)["tree"]["sha"]
        root = self.request("GET", f"/repos/{repo}/git/trees/{tree_sha}")
        if root.get("truncated"):
            raise ValueError("GitHub root tree was truncated; cannot list builds safely")
        uploads = next((entry for entry in root["tree"]
                        if entry["path"] == "strapman-uploads"), None)
        if uploads is None:
            return []
        if uploads["type"] != "tree":
            raise ValueError("The strapman-uploads path is not a directory")
        listing = self.request("GET", f"/repos/{repo}/git/trees/{uploads['sha']}",
                               params={"recursive": "1"})
        if listing.get("truncated"):
            raise ValueError("GitHub upload listing was truncated; cannot claim all builds")
        paths: list[str] = []
        for entry in listing["tree"]:
            path = entry["path"]
            if (entry["type"] == "blob" and path.endswith("/manifest.json")
                    and len(path.split("/")) == 2
                    and all(part not in ("", ".", "..") for part in path.split("/"))):
                paths.append("strapman-uploads/" + path)
        return sorted(set(paths))

    def file_sha(self, repo: str, branch: str, path: str) -> str | None:
        """Current tracked-file Git blob SHA; never treats HTTP failures as absence."""
        repo = parse_repository(repo)
        path = path.strip("/")
        if not path or any(p in ("", ".", "..") for p in path.split("/")):
            raise ValueError("Unsafe remote path")
        try:
            item = self.request("GET", f"/repos/{repo}/contents/{quote(path, safe='/')}",
                                params={"ref": branch})
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise
        if not isinstance(item, dict) or item.get("type") != "file":
            raise FileExistsError(f"GitHub destination is not an ordinary file: {path}")
        return item["sha"]

    def commit_files(self, repo: str, branch: str, files: dict[str, str],
                     message: str, *, replace_paths: set[str] | None = None) -> str:
        """Commit independent blob pointers with branch conflict retries.

        Existing identical files are idempotent; differing remote files are
        rejected except explicitly declared cumulative-staging paths. The
        branch is never force-pushed or rewritten.
        """
        repo = parse_repository(repo)
        if not files:
            raise ValueError("No blob pointers to commit")
        replace_paths = replace_paths or set()
        items = []
        for path, sha in files.items():
            if path.startswith("/") or "\\" in path or ".." in path.split("/") or "" in path.split("/"):
                raise ValueError("Invalid remote path")
            if not re.fullmatch(r"[0-9a-f]{40}", sha):
                raise ValueError("Invalid Git blob SHA")
            items.append({"path": path, "mode": "100644", "type": "blob", "sha": sha})
        if not replace_paths.issubset(files):
            raise ValueError("Replacement exceptions must correspond to submitted files")
        for attempt in range(5):
            parent = self.branch_head(repo, branch)
            pending = []
            for entry in items:
                existing = self.file_sha(repo, branch, entry["path"])
                if existing == entry["sha"]:
                    continue
                if existing is not None and entry["path"] not in replace_paths:
                    raise FileExistsError(f"Refusing to overwrite existing GitHub file: {entry['path']}")
                pending.append(entry)
            if not pending:
                return parent
            old_tree = self.commit_object(repo, parent)["tree"]["sha"]
            tree = self.request("POST", f"/repos/{repo}/git/trees",
                                data={"base_tree": old_tree, "tree": pending}, expected=(201,))
            commit = self.request("POST", f"/repos/{repo}/git/commits",
                                  data={"message": message, "tree": tree["sha"], "parents": [parent]}, expected=(201,))
            try:
                self.request("PATCH", f"/repos/{repo}/git/refs/heads/{quote(branch, safe='/')}",
                             data={"sha": commit["sha"], "force": False})
                return commit["sha"]
            except GitHubError as error:
                if error.status not in (409, 422) or attempt == 4:
                    raise
                time.sleep(0.5 + attempt)
        raise GitHubError(409, "Branch advanced too frequently")
