"""GitHub tree-inventory parser uses deterministic in-memory REST fixtures."""
from __future__ import annotations

import pytest

from strapman.github import GitHub


def test_folder_inventory_walks_exact_directory_without_recursive_listing() -> None:
    github = object.__new__(GitHub)
    github.branch_head = lambda repo, branch: "a" * 40
    github.commit_object = lambda repo, sha: {"tree": {"sha": "r" * 40}}
    tree = {
        "r" * 40: [{"path": "strapman-uploads", "type": "tree", "sha": "s" * 40}],
        "s" * 40: [{"path": "job-id", "type": "tree", "sha": "j" * 40}],
        "j" * 40: [{"path": "chunks", "type": "tree", "sha": "c" * 40}],
        "c" * 40: [{"path": "part-000000", "type": "blob", "sha": "b" * 40},
                    {"path": "part-000001", "type": "blob", "sha": "d" * 40}],
    }
    seen = []
    def request(method, path, **kwargs):
        seen.append(path)
        return {"truncated": False, "tree": tree[path.rsplit("/", 1)[-1]]}
    github.request = request
    assert github.folder_blobs("owner/repo", "main", "strapman-uploads/job-id/chunks") == {
        "part-000000": "b" * 40, "part-000001": "d" * 40}
    assert len(seen) == 4


def test_truncated_remote_tree_fails_closed() -> None:
    github = object.__new__(GitHub)
    github.branch_head = lambda repo, branch: "a" * 40
    github.commit_object = lambda repo, sha: {"tree": {"sha": "r" * 40}}
    github.request = lambda method, path, **kwargs: {"truncated": True, "tree": []}
    with pytest.raises(ValueError, match="truncated"):
        github.folder_blobs("owner/repo", "main", "strapman-uploads/id/chunks")


def test_large_manifest_text_falls_back_to_blob_api() -> None:
    github = object.__new__(GitHub)
    def request(method, path, **kwargs):
        assert "/contents/" in path
        return {"type": "file", "encoding": "none", "sha": "a" * 40}
    github.request = request
    github.get_blob = lambda repo, sha: b'{"format":"strapman-chunks-v1"}\n'
    result = github.read_text("owner/repo", "strapman-uploads/id/manifest.json", "main")
    assert result == ('{"format":"strapman-chunks-v1"}\n', "a" * 40)


def test_create_blob_rejects_mismatched_github_object_id() -> None:
    github = object.__new__(GitHub)
    github.request = lambda *args, **kwargs: {"sha": "f" * 40}
    with pytest.raises(ValueError, match="does not match"):
        github.create_blob("owner/repo", b"payload")


def test_create_blob_accepts_correct_github_object_id() -> None:
    import hashlib
    github = object.__new__(GitHub)
    data = b"payload"
    sha = hashlib.sha1(b"blob 7\0" + data).hexdigest()
    github.request = lambda *args, **kwargs: {"sha": sha}
    assert github.create_blob("owner/repo", data) == sha


def test_repository_file_paths_refuse_traversal_and_invalid_uris():
    from strapman.github import validate_repository_file_path
    assert validate_repository_file_path("src/module.py") == "src/module.py"
    assert validate_repository_file_path("", allow_root=True) == ""
    for path in ("/root.py", "../secrets", "x/../secrets", "x//y", "x\\y", ".git/config", "x\x00.py"):
        with pytest.raises(ValueError):
            validate_repository_file_path(path)


def test_repository_editor_browses_selected_branch_only():
    github = object.__new__(GitHub)
    seen = []
    def request(method, path, **kwargs):
        seen.append((method, path, kwargs.get("params")))
        return [
            {"name": "z.py", "path": "src/z.py", "size": 15, "type": "file"},
            {"name": "nested", "path": "src/nested", "size": 0, "type": "dir"},
            {"name": "a.py", "path": "src/a.py", "size": 9, "type": "file"},
            {"name": "symlink", "path": "src/symlink", "type": "symlink"},
        ]
    github.request = request
    assert [entry["name"] for entry in github.list_directory("alice/repo", "feature", "src")] == [
        "nested", "a.py", "z.py"]
    assert seen == [("GET", "/repos/alice/repo/contents/src", {"ref": "feature"})]


def test_repository_editor_refuses_truncated_folder_listing():
    github = object.__new__(GitHub)
    github.request = lambda *_args, **_kwargs: [{"type": "file", "name": "x"}] * 1000
    with pytest.raises(ValueError, match="1,000"):
        github.list_directory("alice/repo", "main")


def test_remote_code_commit_keeps_optimistic_sha():
    github = object.__new__(GitHub)
    operations = []
    github.request = lambda method, path, **kwargs: (operations.append((method, path, kwargs)), {"content":{"sha":"b" * 40}})[-1]
    github.write_text("alice/repo", "feature", "src/code.py", "print(2)\n", "edit: test", "a" * 40)
    assert operations[0][0] == "PUT"
    assert operations[0][2]["data"]["sha"] == "a" * 40
    assert operations[0][2]["data"]["branch"] == "feature"
    assert operations[0][2]["data"]["message"] == "edit: test"


def test_get_blob_verifies_returned_git_object_id_and_bytes():
    import base64
    import hashlib
    payload = b"\x00binary\xffGitHub\n"
    expected = hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()
    github = object.__new__(GitHub)
    github.request = lambda *_a, **_kw: {
        "encoding": "base64", "content": base64.b64encode(payload).decode(),
        "size": len(payload), "sha": expected}
    assert github.get_blob("alice/repo", expected) == payload
    with pytest.raises(ValueError, match="requested SHA"):
        github.get_blob("alice/repo", "f" * 40)
    with pytest.raises(ValueError, match="Invalid requested"):
        github.get_blob("alice/repo", "../../other")


def test_get_blob_rejects_same_size_corruption():
    import base64
    import hashlib
    original, tampered = b"original-part", b"tampereD-part"
    assert len(original) == len(tampered)
    expected = hashlib.sha1(f"blob {len(original)}\0".encode() + original).hexdigest()
    github = object.__new__(GitHub)
    github.request = lambda *_a, **_kw: {
        "encoding": "base64", "content": base64.b64encode(tampered).decode(),
        "size": len(tampered), "sha": expected}
    with pytest.raises(ValueError, match="requested SHA"):
        github.get_blob("alice/repo", expected)


def test_read_text_requires_sha_consistent_with_contents_response():
    import base64
    import hashlib
    body = b"hello\n"
    actual = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
    github = object.__new__(GitHub)
    github.request = lambda *_a, **_kw: {
        "type": "file", "encoding": "base64", "sha": actual,
        "content": base64.b64encode(body).decode() + "\n"}
    assert github.read_text("alice/repo", "README.md", "main") == ("hello\n", actual)
    github.request = lambda *_a, **_kw: {
        "type": "file", "encoding": "base64", "sha": "f" * 40,
        "content": base64.b64encode(body).decode()}
    with pytest.raises(ValueError, match="blob SHA"):
        github.read_text("alice/repo", "README.md", "main")
