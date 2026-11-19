"""Tests for protected post-release synchronization using real Git history."""

import json
import runpy
import subprocess
from pathlib import Path

import pytest

sync = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/sync_develop.py")
)
synchronize = sync["synchronize"]


def git(*args: str) -> str:
    """Execute Git in the temporary repository."""
    return subprocess.check_output(["git", *args], text=True).strip()


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """Create divergent main and develop branches and a stable release tag."""
    remote = tmp_path / "remote.git"
    git("init", "--bare", str(remote))
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    git("init", "-b", "main")
    git("config", "user.name", "Test")
    git("config", "user.email", "test@example.com")
    git("remote", "add", "origin", str(remote))
    git("commit", "--allow-empty", "-m", "base")
    git("branch", "develop")
    Path("release.txt").write_text("release")
    git("add", "release.txt")
    git("commit", "-m", "release")
    git("tag", "v0.4.0")
    git("switch", "develop")
    Path("feature.txt").write_text("feature")
    git("add", "feature.txt")
    git("commit", "-m", "feature")
    git("push", "origin", "main", "develop", "--tags")
    calls = []
    prs = []

    def fake_run(*args):
        if args[0] == "git":
            return git(*args[1:])
        calls.append(args)
        if args[1:3] == ("release", "view"):
            return json.dumps({"isDraft": False, "isPrerelease": False})
        if args[1:3] == ("pr", "list"):
            return json.dumps(prs)
        if args[1:3] == ("pr", "create"):
            prs.append({"number": 42})
            return "https://github.com/example/repo/pull/42"
        if args[1:3] == ("pr", "merge"):
            return ""
        raise AssertionError(args)

    monkeypatch.setitem(synchronize.__globals__, "run", fake_run)
    return calls


def test_create_sync(repository):
    """Preserve both histories and request protected auto-merge."""
    synchronize("v0.4.0")
    assert Path("release.txt").exists()
    assert Path("feature.txt").exists()
    assert git("rev-parse", "origin/develop") != git("rev-parse", "HEAD")
    assert any(c[1:3] == ("pr", "create") for c in repository)
    assert repository[-1][-2:] == ("--auto", "--merge")


def test_retry(repository):
    """Reuse the branch and existing pull request on a retry."""
    synchronize("v0.4.0")
    synchronize("v0.4.0")
    assert sum(c[1:3] == ("pr", "create") for c in repository) == 1
    assert repository[-1][3] == "42"


def test_already_synchronized(repository):
    """Do not create a pull request when develop contains the release."""
    git("merge", "--no-edit", "v0.4.0")
    git("push", "origin", "develop")
    synchronize("v0.4.0")
    assert len(repository) == 1


def test_invalid_tag(repository):
    """Reject non-release input before contacting GitHub."""
    with pytest.raises(ValueError, match="Expected vX.Y.Z"):
        synchronize("main")
    assert not repository


def test_conflict(repository):
    """Stop before publishing a branch when histories conflict."""
    Path("release.txt").write_text("different")
    git("add", "release.txt")
    git("commit", "-m", "conflict")
    git("push", "origin", "develop")
    with pytest.raises(subprocess.CalledProcessError):
        synchronize("v0.4.0")
    assert len(repository) == 1
    assert not git("ls-remote", "--heads", "origin", "sync/release-v0.4.0")


def test_develop_advances(repository):
    """Refresh an existing synchronization branch without losing new work."""
    synchronize("v0.4.0")
    git("switch", "develop")
    Path("new.txt").write_text("new feature")
    git("add", "new.txt")
    git("commit", "-m", "new feature")
    git("push", "origin", "develop")
    synchronize("v0.4.0")
    assert Path("new.txt").exists()
    assert sum(c[1:3] == ("pr", "create") for c in repository) == 1


def test_unpublished_release(repository, monkeypatch):
    """Reject draft releases before changing Git history."""
    monkeypatch.setitem(
        synchronize.__globals__,
        "run",
        lambda *args: json.dumps({"isDraft": True, "isPrerelease": False}),
    )
    with pytest.raises(ValueError, match="published stable release"):
        synchronize("v0.4.0")
    assert not git("ls-remote", "--heads", "origin", "sync/release-v0.4.0")
