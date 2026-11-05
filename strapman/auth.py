"""Device-code OAuth and per-user GitHub CLI login helpers.

No OAuth client secret is required or stored. The public client ID belongs to
an OAuth App that must have device flow enabled by its owner.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from .core import app_directory

DEVICE_ENDPOINT = "https://github.com/login/device/code"
TOKEN_ENDPOINT = "https://github.com/login/oauth/access_token"
VERIFY_URI = "https://github.com/login/device"
RELEASE_API = "https://api.github.com/repos/cli/cli/releases/latest"
MAX_ARCHIVE = 100 * 1024 * 1024
MIN_INSTALL_FREE = 512 * 1024 * 1024


class AuthError(RuntimeError):
    pass


class AuthCancelled(AuthError):
    pass


@dataclass(frozen=True)
class DeviceCode:
    code: str
    device_code: str
    expires_at: float
    poll_interval: int


class DeviceAuthorization:
    """GitHub OAuth App device grant; one authorization per user-initiated action."""

    def __init__(self, client_id: str, scope: str = "repo read:org", session=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", client_id):
            raise AuthError("Enter a valid GitHub OAuth App client ID in Settings")
        self.client_id = client_id
        self.scope = scope
        self.session = session or requests.Session()

    def _post(self, url: str, fields: dict) -> dict:
        try:
            response = self.session.post(
                url, data=fields, headers={"Accept": "application/json", "User-Agent": "Strapman/0.2"},
                timeout=(10, 20), allow_redirects=False,
            )
            response.raise_for_status()
            value = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise AuthError("GitHub sign-in request failed; check the connection and try again") from exc
        if not isinstance(value, dict):
            raise AuthError("Unexpected GitHub authentication response")
        return value

    def begin(self) -> DeviceCode:
        value = self._post(DEVICE_ENDPOINT, {"client_id": self.client_id, "scope": self.scope})
        if value.get("error"):
            raise AuthError("GitHub refused the device-code request; review the OAuth App settings")
        if value.get("verification_uri") != VERIFY_URI:
            raise AuthError("Unexpected GitHub verification destination; sign-in cancelled")
        code = str(value.get("user_code", ""))
        device = str(value.get("device_code", ""))
        if not re.fullmatch(r"[A-Z0-9]{4}-[A-Z0-9]{4}", code) or len(device) < 20:
            raise AuthError("GitHub returned an invalid device authorization code")
        expires = int(value.get("expires_in", 0))
        interval = max(5, int(value.get("interval", 5)))
        if not 30 <= expires <= 1800:
            raise AuthError("Unexpected device-code expiration")
        return DeviceCode(code, device, time.monotonic() + expires, interval)

    def await_token(self, ticket: DeviceCode, cancel: threading.Event,
                    notice: Callable[[str], None] | None = None) -> str:
        interval = ticket.poll_interval
        while time.monotonic() < ticket.expires_at:
            if cancel.wait(min(interval, max(0.0, ticket.expires_at - time.monotonic()))):
                raise AuthCancelled("Sign-in cancelled")
            if time.monotonic() >= ticket.expires_at:
                break
            value = self._post(TOKEN_ENDPOINT, {
                "client_id": self.client_id, "device_code": ticket.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            })
            if cancel.is_set():
                raise AuthCancelled("Sign-in cancelled")
            if value.get("access_token"):
                if value.get("token_type", "").lower() != "bearer":
                    raise AuthError("Unexpected GitHub token type")
                return str(value["access_token"])
            error = value.get("error", "")
            if error == "authorization_pending":
                if notice:
                    notice("Waiting for approval in GitHub…")
            elif error == "slow_down":
                interval = max(interval + 5, int(value.get("interval", interval + 5)))
                if notice:
                    notice("GitHub requested a slower confirmation check…")
            elif error in ("expired_token", "access_denied"):
                raise AuthError("GitHub authorization expired or was declined")
            else:
                raise AuthError("GitHub device sign-in failed; check the OAuth App settings")
        raise AuthError("Device code expired; request a new code")


def git_credential_token(username: str = "") -> str:
    """Query the installed Git credential helper without prompting or persisting tokens.

    Git for Windows normally includes Git Credential Manager. This is optional:
    native OAuth device sign-in never requires Git or GitHub CLI. A returned
    credential is only a *candidate*, and must pass GitHub /user validation.
    """
    git = shutil.which("git")
    if not git:
        return ""
    if username and not re.fullmatch(r"[A-Za-z0-9-]{1,39}", username):
        return ""
    fields = "protocol=https\nhost=github.com\n"
    if username:
        fields += f"username={username}\n"
    fields += "\n"
    environment = dict(os.environ)
    environment.update({
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "GIT_ASKPASS": "",
        "SSH_ASKPASS": "",
    })
    try:
        result = subprocess.run(
            [git, "-c", "credential.interactive=never", "credential", "fill"],
            input=fields, capture_output=True, text=True, encoding="utf-8",
            errors="replace", env=environment, timeout=10, check=False,
        )
        if result.returncode != 0:
            return ""
        values = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition("=")
            if separator and key in ("protocol", "host", "username", "password"):
                values[key] = value
        if values.get("protocol") != "https" or values.get("host") != "github.com":
            return ""
        token = values.get("password", "")
        return token if token and len(token) <= 4096 and not any(c in token for c in "\r\n\x00") else ""
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return ""


def bundled_oauth_client_id(config_path: Path | None = None) -> str:
    """Public OAuth client ID configured once by the publisher, never a secret.

    The optional config file is published alongside the program; setting the
    STRAPMAN_OAUTH_CLIENT_ID environment variable can override it in testing.
    """
    env_id = os.environ.get("STRAPMAN_OAUTH_CLIENT_ID", "").strip()
    if env_id:
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", env_id):
            raise AuthError("Invalid public GitHub OAuth client ID configuration")
        return env_id
    path = config_path or Path(__file__).with_name("oauth_app.json")
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AuthError("Invalid public GitHub OAuth App configuration file") from exc
    if not isinstance(data, dict) or set(data) != {"client_id"} or not isinstance(data["client_id"], str):
        raise AuthError("OAuth config must contain only the public client_id")
    client_id = data["client_id"].strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", client_id):
        raise AuthError("Invalid public GitHub OAuth client ID configuration")
    return client_id


def github_cli_path() -> str | None:
    """Use a system installation or Strapman's verified, user-local installation."""
    path = shutil.which("gh")
    if path:
        return path
    local = app_directory() / "tools" / ("gh.exe" if sys.platform == "win32" else "gh")
    return str(local) if local.is_file() else None


def github_cli_token(username: str = "") -> str:
    exe = github_cli_path()
    if not exe:
        return ""
    args = [exe, "auth", "token", "--hostname", "github.com"]
    if username:
        args += ["--user", username]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20, check=False)
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def github_cli_accounts() -> list[dict]:
    exe = github_cli_path()
    if not exe:
        return []
    try:
        result = subprocess.run(
            [exe, "auth", "status", "--json", "hosts", "--no-refresh"],
            capture_output=True, text=True, timeout=20, check=False,
        )
        data = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []
    hosts = data.get("hosts", {})
    accounts = hosts.get("github.com", []) if isinstance(hosts, dict) else []
    if isinstance(accounts, dict):
        accounts = [accounts]
    result = []
    for account in accounts:
        if not isinstance(account, dict):
            continue
        login = account.get("login", "")
        if re.fullmatch(r"[A-Za-z0-9-]{1,39}", str(login)) and account.get("state", "success") not in (
            "refresh_expired", "invalid", "missing", "expired", "error"
        ):
            result.append({"login": login, "active": bool(account.get("active", False))})
    return result


def github_cli_switch(username: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", username):
        raise AuthError("Invalid GitHub account name")
    exe = github_cli_path()
    if not exe:
        raise AuthError("GitHub CLI is not installed")
    result = subprocess.run([exe, "auth", "switch", "--hostname", "github.com", "--user", username],
                            capture_output=True, timeout=30, check=False)
    if result.returncode != 0:
        raise AuthError("GitHub CLI could not switch to the selected account")


def github_cli_logout(username: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", username):
        raise AuthError("Invalid GitHub account name")
    exe = github_cli_path()
    if not exe:
        raise AuthError("GitHub CLI is not installed")
    result = subprocess.run([exe, "auth", "logout", "--hostname", "github.com", "--user", username],
                            capture_output=True, timeout=30, check=False)
    if result.returncode != 0:
        raise AuthError("GitHub CLI could not log out of the selected account")


def _release_suffix() -> str:
    arch = platform.machine().lower()
    mapping = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}
    if arch not in mapping:
        raise AuthError("Automatic GitHub CLI installation supports x86-64 and ARM64")
    if sys.platform == "win32":
        return f"_windows_{mapping[arch]}.zip"
    if sys.platform.startswith("linux"):
        return f"_linux_{mapping[arch]}.tar.gz"
    raise AuthError("Automatic GitHub CLI installation supports Windows and Linux")


def install_github_cli(progress: Callable[[int, int, str], None] | None = None) -> str:
    """Install only the official gh executable under user app-data; never elevate.

    Check free space before fetching any asset. Verify its API-published SHA-256,
    validate the archive member and limit decompression size.
    """
    existing = github_cli_path()
    if existing:
        return existing
    folder = app_directory() / "tools"
    folder.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(folder).free
    if free < MIN_INSTALL_FREE:
        raise AuthError(f"Not enough free disk space for GitHub CLI (requires 512 MiB; available {free // 1048576} MiB)")
    suffix = _release_suffix()
    try:
        r = requests.get(RELEASE_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "Strapman/0.2"}, timeout=(10, 30))
        r.raise_for_status()
        releases = r.json()
        matches = [a for a in releases["assets"] if a.get("name", "").endswith(suffix)]
        if len(matches) != 1:
            raise AuthError("Official GitHub CLI archive for this platform was not found")
        asset = matches[0]
        expected = str(asset.get("digest", ""))
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
            raise AuthError("GitHub CLI release has no verifiable SHA-256 digest")
        if int(asset.get("size", 0)) > MAX_ARCHIVE:
            raise AuthError("GitHub CLI download exceeds safety limit")
        url = str(asset["browser_download_url"])
        if not url.startswith("https://github.com/cli/cli/releases/download/"):
            raise AuthError("Unexpected GitHub CLI download host or path")
        with tempfile.TemporaryDirectory(prefix="strapman-gh-", dir=folder) as temp:
            if Path(asset["name"]).name != asset["name"]:
                raise AuthError("Unsafe GitHub CLI release asset filename")
            archive = Path(temp) / asset["name"]
            sha = hashlib.sha256()
            count = 0
            with requests.get(url, stream=True, timeout=(10, 90), headers={"User-Agent": "Strapman/0.2"}) as stream:
                stream.raise_for_status()
                with archive.open("wb") as out:
                    for block in stream.iter_content(chunk_size=1024 * 256):
                        if not block:
                            continue
                        count += len(block)
                        if count > MAX_ARCHIVE:
                            raise AuthError("GitHub CLI download exceeded size limit")
                        out.write(block)
                        sha.update(block)
                        if progress:
                            progress(count, int(asset["size"]), "Downloading GitHub CLI")
            if sha.hexdigest() != expected[7:]:
                raise AuthError("Downloaded GitHub CLI failed SHA-256 verification")
            binary_name = "gh.exe" if sys.platform == "win32" else "gh"
            destination = folder / binary_name
            temporary_exe = folder / (".gh.exe.incomplete" if sys.platform == "win32" else ".gh.incomplete")
            if archive.suffix == ".zip":
                with zipfile.ZipFile(archive) as z:
                    matches = [m for m in z.infolist() if m.filename.replace("\\", "/").endswith("/bin/gh.exe") and not m.is_dir()]
                    if len(matches) != 1 or matches[0].file_size > 120 * 1024 * 1024:
                        raise AuthError("Unsafe or unexpected GitHub CLI ZIP")
                    with z.open(matches[0]) as src, temporary_exe.open("wb") as out:
                        shutil.copyfileobj(src, out, 1024 * 1024)
            else:
                with tarfile.open(archive, "r:gz") as tar:
                    matches = [m for m in tar.getmembers() if m.name.endswith("/bin/gh") and m.isfile()]
                    if len(matches) != 1 or matches[0].size > 120 * 1024 * 1024:
                        raise AuthError("Unsafe or unexpected GitHub CLI archive")
                    source = tar.extractfile(matches[0])
                    if source is None:
                        raise AuthError("GitHub CLI executable was not present")
                    with source, temporary_exe.open("wb") as out:
                        shutil.copyfileobj(source, out, 1024 * 1024)
            if sys.platform != "win32":
                temporary_exe.chmod(0o700)
            version = subprocess.run([str(temporary_exe), "--version"], capture_output=True,
                                     text=True, timeout=15, check=False)
            if version.returncode != 0 or not version.stdout.startswith("gh version"):
                temporary_exe.unlink(missing_ok=True)
                raise AuthError("Downloaded GitHub CLI did not pass its executable self-check")
            os.replace(temporary_exe, destination)
            if progress:
                progress(1, 1, "GitHub CLI verified and installed")
            return str(destination)
    except (requests.RequestException, OSError, KeyError, ValueError, zipfile.BadZipFile, tarfile.TarError) as exc:
        raise AuthError("Automatic GitHub CLI installation failed; use the native code flow or install gh manually") from exc
