from __future__ import annotations

import json
import threading
from dataclasses import dataclass

import pytest

from strapman.auth import (
    AuthCancelled, AuthError, DeviceAuthorization, DeviceCode,
    github_cli_accounts, github_cli_token, install_github_cli,
)


class Response:
    def __init__(self, body):
        self.body = body

    def raise_for_status(self):
        return None

    def json(self):
        return self.body


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response(self.responses.pop(0))


def ticket():
    import time
    return DeviceCode("ABCD-1234", "d" * 40, time.monotonic() + 300, 5)


class ImmediateEvent:
    def __init__(self):
        self.triggered = False

    def wait(self, _):
        return self.triggered

    def is_set(self):
        return self.triggered


def test_native_device_code_success_and_polling():
    fake = Session(
        {"user_code": "ABCD-1234", "device_code": "d" * 40,
         "expires_in": 900, "interval": 5, "verification_uri": "https://github.com/login/device"},
        {"error": "authorization_pending"},
        {"access_token": "sensitive-token-never-log", "token_type": "bearer"},
    )
    auth = DeviceAuthorization("Iv1_TEST_CLIENT", session=fake)
    t = auth.begin()
    assert t.code == "ABCD-1234"
    assert len(t.device_code) == 40
    assert auth.await_token(t, ImmediateEvent()) == "sensitive-token-never-log"
    assert fake.calls[0][0].endswith("/login/device/code")
    assert fake.calls[1][0].endswith("/login/oauth/access_token")
    assert "client_secret" not in fake.calls[0][1]["data"]
    assert "client_secret" not in fake.calls[1][1]["data"]


def test_native_device_code_rejects_unexpected_url():
    fake = Session({"user_code": "ABCD-1234", "device_code": "d" * 40,
                    "expires_in": 900, "verification_uri": "https://evil.example/login/device"})
    with pytest.raises(AuthError, match="Unexpected GitHub verification destination"):
        DeviceAuthorization("Iv1_TEST_CLIENT", session=fake).begin()


def test_native_device_login_declined_and_never_reports_code():
    fake = Session({"error": "access_denied"})
    with pytest.raises(AuthError, match="declined") as ex:
        DeviceAuthorization("Iv1_TEST_CLIENT", session=fake).await_token(ticket(), ImmediateEvent())
    assert "d" * 40 not in str(ex.value)


def test_native_device_flow_cancelled_without_poll():
    event = ImmediateEvent()
    event.triggered = True
    fake = Session()
    with pytest.raises(AuthCancelled):
        DeviceAuthorization("Iv1_TEST_CLIENT", session=fake).await_token(ticket(), event)
    assert fake.calls == []


def test_device_flow_rejects_invalid_app_id():
    with pytest.raises(AuthError, match="OAuth App client ID"):
        DeviceAuthorization("https://example.com/steal")


def test_cli_account_selection_does_not_read_tokens_in_status(monkeypatch):
    import strapman.auth as auth
    class Result:
        returncode = 0
        stdout = json.dumps({"hosts": {"github.com": [
            {"login": "one-user", "active": True, "state": "success", "tokenSource": "keyring"},
            {"login": "two-user", "active": False, "state": "success", "tokenSource": "keyring"},
            {"login": "error-user", "state": "refresh_expired"}
        ]}})
    def run(args, **kwargs):
        assert "--show-token" not in args
        assert "--no-refresh" in args
        return Result()
    monkeypatch.setattr(auth, "github_cli_path", lambda: "/bin/gh")
    monkeypatch.setattr(auth.subprocess, "run", run)
    assert github_cli_accounts() == [
        {"login": "one-user", "active": True},
        {"login": "two-user", "active": False},
    ]


def test_cli_token_pinned_to_chosen_user(monkeypatch):
    import strapman.auth as auth
    class Result:
        returncode = 0
        stdout = "not-real-token\n"
    def run(args, **kwargs):
        assert args[-2:] == ["--user", "other-user"]
        return Result()
    monkeypatch.setattr(auth, "github_cli_path", lambda: "/bin/gh")
    monkeypatch.setattr(auth.subprocess, "run", run)
    assert github_cli_token("other-user") == "not-real-token"


def test_installer_space_check_before_network(monkeypatch, tmp_path):
    import strapman.auth as auth
    monkeypatch.setattr(auth, "github_cli_path", lambda: None)
    monkeypatch.setattr(auth, "app_directory", lambda: tmp_path)
    monkeypatch.setattr(auth.shutil, "disk_usage", lambda _: type("Space", (), {"free": 10})())
    monkeypatch.setattr(auth.requests, "get", lambda *a, **kw: pytest.fail("No network before disk gate"))
    with pytest.raises(AuthError, match="Not enough free disk space"):
        install_github_cli()


def test_git_credential_helper_reuses_existing_token_without_prompts(monkeypatch):
    import os
    import strapman.auth as auth
    token = "existing-helper-token"
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert command == ["/usr/bin/git", "-c", "credential.interactive=never", "credential", "fill"]
        assert kwargs["input"] == "protocol=https\nhost=github.com\n\n"
        assert kwargs["env"]["GCM_INTERACTIVE"] == "Never"
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kwargs["env"]["GIT_ASKPASS"] == ""
        assert kwargs["env"]["SSH_ASKPASS"] == ""
        assert kwargs["timeout"] == 10
        return type("Reply", (), {"returncode": 0,
            "stdout": f"protocol=https\nhost=github.com\nusername=someone\npassword={token}\n"})()

    monkeypatch.setattr(auth.shutil, "which", lambda name: "/usr/bin/git" if name == "git" else None)
    monkeypatch.setattr(auth.subprocess, "run", run)
    assert auth.git_credential_token() == token
    assert len(calls) == 1


def test_git_credential_helper_optional_and_pinned_username(monkeypatch):
    import strapman.auth as auth
    monkeypatch.setattr(auth.shutil, "which", lambda _: None)
    monkeypatch.setattr(auth.subprocess, "run", lambda *a, **kw: pytest.fail("No git installed; no subprocess"))
    assert auth.git_credential_token() == ""
    assert auth.git_credential_token("bad\nname") == ""

    monkeypatch.setattr(auth.shutil, "which", lambda _: "/usr/bin/git")
    class Reply:
        returncode = 0
        stdout = "protocol=https\nhost=github.com\nusername=alice\npassword=credential\n"
    def run(command, **kwargs):
        assert "username=alice\n" in kwargs["input"]
        return Reply()
    monkeypatch.setattr(auth.subprocess, "run", run)
    assert auth.git_credential_token("alice") == "credential"


def test_git_credential_helper_fails_closed_on_invalid_response_or_error(monkeypatch):
    import strapman.auth as auth
    monkeypatch.setattr(auth.shutil, "which", lambda _: "git")
    for text in ("protocol=http\nhost=github.com\npassword=leak\n",
                 "protocol=https\nhost=not-github.com\npassword=leak\n",
                 "protocol=https\nhost=github.com\n",
                 "protocol=https\nhost=github.com\npassword=\n"):
        monkeypatch.setattr(auth.subprocess, "run", lambda *a, **k: type("R", (), {"returncode":0,"stdout":text})())
        assert auth.git_credential_token() == ""
    monkeypatch.setattr(auth.subprocess, "run", lambda *a, **k: type("R", (), {"returncode":1,"stdout":"protocol=https\nhost=github.com\npassword=leak\n"})())
    assert auth.git_credential_token() == ""
    def timeout(*a, **k):
        raise auth.subprocess.TimeoutExpired("git", 10)
    monkeypatch.setattr(auth.subprocess, "run", timeout)
    assert auth.git_credential_token() == ""


def test_bundled_public_oauth_id_config_no_secret(monkeypatch, tmp_path):
    import strapman.auth as auth
    monkeypatch.delenv("STRAPMAN_OAUTH_CLIENT_ID", raising=False)
    file = tmp_path / "oauth_app.json"
    assert auth.bundled_oauth_client_id(file) == ""
    file.write_text(json.dumps({"client_id": "Iv1_PUBLIC_ID_12345"}))
    assert auth.bundled_oauth_client_id(file) == "Iv1_PUBLIC_ID_12345"
    file.write_text(json.dumps({"client_id": "Iv1_PUBLIC_ID_12345", "client_secret": "NOT_ALLOWED"}))
    with pytest.raises(AuthError, match="only the public client_id"):
        auth.bundled_oauth_client_id(file)
    file.write_text("{}")
    with pytest.raises(AuthError, match="only the public client_id"):
        auth.bundled_oauth_client_id(file)
    monkeypatch.setenv("STRAPMAN_OAUTH_CLIENT_ID", "Iv1_ENV_PUBLIC")
    assert auth.bundled_oauth_client_id(file) == "Iv1_ENV_PUBLIC"
    monkeypatch.setenv("STRAPMAN_OAUTH_CLIENT_ID", "javascript:bad")
    with pytest.raises(AuthError, match="Invalid public"):
        auth.bundled_oauth_client_id(file)


def test_github_rest_client_can_use_git_credentials_without_cli(monkeypatch):
    import strapman.github as github
    monkeypatch.delenv("STRAPMAN_GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(github, "saved_token", lambda *_: "")
    monkeypatch.setattr(github, "cli_token", lambda *_: pytest.fail("No CLI required for existing Git"))
    monkeypatch.setattr(github, "git_credential_token", lambda *_: "existing-verified-candidate")
    client = github.GitHub()
    assert client.token == "existing-verified-candidate"
    assert github.GitHub("explicit-user-token").token == "explicit-user-token"
