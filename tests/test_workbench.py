"""Workbench must not execute edited code or overwrite without intent."""
from pathlib import Path
import pytest
from strapman.workbench import TextWorkbench, check_syntax


def test_syntax_is_static(tmp_path):
    marker = tmp_path / "ran.txt"
    payload = f"open({str(marker)!r}, 'w').write('executed')\n"
    assert check_syntax(payload, "check.py")["valid"] is True
    assert not marker.exists()
    assert check_syntax("def bad(:\n pass", "broken.py")["valid"] is False
    assert check_syntax('{"active": true}', "settings.json")["valid"] is True
    assert check_syntax("[", "settings.json")["valid"] is False
    assert check_syntax("x = 2", "config.toml")["valid"] is True
    assert check_syntax("anything", "README.md")["valid"] is None


def test_workbench_backup_and_explicit_save(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("A = 1\n", encoding="utf-8")
    work = TextWorkbench()
    assert work.open(path) == "A = 1\n"
    assert "-A = 1" in work.diff("A = 2\n")
    work.save("A = 2\n")
    assert path.read_text() == "A = 2\n"
    backups = list(tmp_path.glob("app.py.strapman-*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text() == "A = 1\n"


def test_workbench_rejects_external_changes_and_overwrite(tmp_path):
    path = tmp_path / "script.json"
    path.write_text("{}")
    work = TextWorkbench()
    work.open(path)
    path.write_text('{"external":true}')
    with pytest.raises(FileExistsError):
        work.save('{"mine":true}')
    assert path.read_text() == '{"external":true}'
    with pytest.raises(FileExistsError):
        work.save_as("copy", path)
    out = work.save_as('{"new":true}', tmp_path / "new.json")
    assert out.read_text() == '{"new":true}'


def test_binary_not_opened(tmp_path):
    path = tmp_path / "data.bin"
    path.write_bytes(b"\x00\xff")
    with pytest.raises(ValueError, match="binary"):
        TextWorkbench().open(path)


def test_remote_editor_requires_same_account_repo_branch_file_and_sha():
    from strapman.workbench import RemoteTextWorkbench
    work = RemoteTextWorkbench()
    work.bind("alice", "alice/sample", "main", "src/code.py", "a = 1\n", "a" * 40)
    assert work.dirty("a = 2\n")
    assert "+a = 2" in work.diff("a = 2\n")
    assert work.prepare_commit("alice", "alice/sample", "main", "src/code.py", "a = 2\n") == "a" * 40
    for login, repo, branch, path in [
        ("bob", "alice/sample", "main", "src/code.py"),
        ("alice", "bob/sample", "main", "src/code.py"),
        ("alice", "alice/sample", "dev", "src/code.py"),
        ("alice", "alice/sample", "main", "src/other.py"),
    ]:
        with pytest.raises(ValueError, match="changed"):
            work.prepare_commit(login, repo, branch, path, "a = 2\n")
    with pytest.raises(ValueError, match="no changes"):
        work.prepare_commit("alice", "alice/sample", "main", "src/code.py", "a = 1\n")


def test_new_github_file_must_be_explicitly_populated():
    from strapman.workbench import RemoteTextWorkbench
    work = RemoteTextWorkbench()
    work.bind("alice", "alice/repo", "main", "docs/new.md", "", "")
    assert work.prepare_commit("alice", "alice/repo", "main", "docs/new.md", "# New\n") == ""
    with pytest.raises(ValueError, match="Unsafe"):
        work.bind("alice", "alice/repo", "main", "../secret", "", "")


def test_local_unittest_runner_requires_explicit_directory(tmp_path):
    from strapman.workbench import run_local_tests
    folder = tmp_path / "suite"
    folder.mkdir()
    (folder / "test_hello.py").write_text(
        "import unittest\nclass Demo(unittest.TestCase):\n"
        "    def test_true(self): self.assertTrue(True)\n", encoding="utf-8")
    result = run_local_tests(folder, timeout_seconds=15)
    assert result["passed"] is True
    assert result["tests"] == 1
    assert result["exit_code"] == 0
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="No unittest tests"):
        run_local_tests(empty)


def test_local_runner_supports_pytest_when_already_available(tmp_path):
    import importlib.util
    from strapman.workbench import run_local_tests
    if importlib.util.find_spec("pytest") is None:
        pytest.skip("pytest is not installed in this Python environment")
    folder = tmp_path / "project"
    folder.mkdir()
    (folder / "test_small.py").write_text("def test_success():\n    assert 3 * 7 == 21\n")
    result = run_local_tests(folder, timeout_seconds=30, framework="pytest")
    assert result["framework"] == "pytest"
    assert result["passed"] is True
    assert result["tests"] == 1
    auto = run_local_tests(folder, timeout_seconds=30, framework="auto")
    assert auto["framework"] == "pytest"
    assert auto["tests"] == 1


def test_local_runner_does_not_claim_failing_pytest_suite_passed(tmp_path):
    from strapman.workbench import run_local_tests
    folder = tmp_path / "tests"
    folder.mkdir()
    (folder / "test_failure.py").write_text("def test_failure():\n    assert 1 == 2\n")
    result = run_local_tests(folder, timeout_seconds=30, framework="pytest")
    assert result["framework"] == "pytest"
    assert result["passed"] is False
    assert result["exit_code"] != 0
    assert result["tests"] == 1
    with pytest.raises(ValueError, match="Test framework"):
        run_local_tests(folder, framework="nosuchframework")
