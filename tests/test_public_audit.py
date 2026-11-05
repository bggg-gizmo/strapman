"""Privacy gate covers current source, credential patterns, and recorded history."""
from pathlib import Path
import subprocess
import sys

from tools.public_audit import audit, validate_bytes, validate_file


def test_public_audit_accepts_safe_source_tree(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Generic public app\n", encoding="utf-8")
    (tmp_path / "src.py").write_text("print('safe source')\n", encoding="utf-8")
    count, findings = audit(tmp_path, False)
    assert count == 2
    assert findings == []


def test_public_audit_flags_secrets_home_paths_and_private_artifacts(tmp_path: Path) -> None:
    (tmp_path / "secrets.py").write_bytes(b'ghp_' + b'Q' * 35 + b'\n' + b'C:\\Users\\privateuser\\Desktop\\confidential.txt')
    (tmp_path / "archive.zip").write_bytes(b"not an appropriate public source artifact")
    _, findings = audit(tmp_path, False)
    assert any("GitHub token" in f for f in findings)
    assert any("Home-folder path" in f for f in findings)
    assert any("Private or archive" in f for f in findings)


def test_public_audit_allows_github_noreply_commit_mail() -> None:
    assert validate_bytes(b"example@users.noreply.github.com") == []
    assert "Real-looking email address" in validate_bytes(b"person" + b"@" + b"example.com")


def test_history_audit_detects_removed_secrets(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email",
                    "123+tester@users.noreply.github.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Tester"], check=True)
    file = tmp_path / "README.md"
    file.write_bytes(b"temporary ghp_" + b"Z" * 30)
    subprocess.run(["git", "-C", str(tmp_path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)
    file.write_text("# Safe current contents\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qam", "sanitize"], check=True)
    assert audit(tmp_path, False)[1] == []
    count, findings = audit(tmp_path, True)
    assert count >= 3
    assert any("HISTORY:README.md: GitHub token" in f for f in findings)


def test_source_only_history_gate_is_explicit(tmp_path: Path) -> None:
    import pytest
    with pytest.raises(RuntimeError, match="Git checkout"):
        audit(tmp_path, True)
