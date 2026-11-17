"""Tests for release metadata validation."""

import json
import runpy
from pathlib import Path

import pytest

release_notes = runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "scripts/release.py")
)["release_notes"]


@pytest.fixture
def release_root(tmp_path: Path) -> Path:
    """Create a minimal consistent release checkout."""
    (tmp_path / "frontend").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "cmf-dev-studio"\nversion = "0.3.0"\n'
    )
    (tmp_path / "uv.lock").write_text(
        'version = 1\n[[package]]\nname = "other"\nversion = "0.2.1"\n'
        '[[package]]\nname = "cmf-dev-studio"\nversion = "0.3.0"\n'
    )
    (tmp_path / "frontend/package.json").write_text(json.dumps({"version": "0.3.0"}))
    (tmp_path / "frontend/package-lock.json").write_text(
        json.dumps({"version": "0.3.0", "packages": {"": {"version": "0.3.0"}}})
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "## [Unreleased]\n\n## [0.3.0] - 2026-11-17\n\n"
        "### Added\n\n- JVM support.\n\n## [0.2.1]\n\n- Old notes.\n"
    )
    return tmp_path


def test_release_notes(release_root: Path) -> None:
    """Extract only the requested release section."""
    assert release_notes(release_root, "release/v0.3.0") == (
        "0.3.0",
        "### Added\n\n- JVM support.",
    )


@pytest.mark.parametrize(
    "branch",
    [
        "main",
        "feature/release",
        "release/v03.0.0",
        "release/v0.3.0-rc1",
        "release/v0.3.0/extra",
    ],
)
def test_invalid_branch(release_root: Path, branch: str) -> None:
    """Reject branches outside the stable release convention."""
    with pytest.raises(ValueError, match="Expected release"):
        release_notes(release_root, branch)


@pytest.mark.parametrize(
    "filename",
    [
        "pyproject.toml",
        "uv.lock",
        "frontend/package.json",
        "frontend/package-lock.json",
    ],
)
def test_version_mismatch(release_root: Path, filename: str) -> None:
    """Reject inconsistent metadata or lockfiles."""
    path = release_root / filename
    path.write_text(path.read_text().replace("0.3.0", "0.3.1"))
    with pytest.raises(ValueError, match="expected 0.3.0"):
        release_notes(release_root, "release/v0.3.0")


def test_npm_root_mismatch(release_root: Path) -> None:
    """Validate the root package entry independently."""
    path = release_root / "frontend/package-lock.json"
    data = json.loads(path.read_text())
    data["packages"][""]["version"] = "0.3.1"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="root"):
        release_notes(release_root, "release/v0.3.0")


@pytest.mark.parametrize(
    "content",
    [
        "## [Unreleased]\n",
        "## [0.3.0] - 2026-11-17\n",
        "## [0.3.0] - 2026-11-17\n- One\n## [0.3.0] - 2026-11-17\n- Two",
    ],
)
def test_invalid_changelog(release_root: Path, content: str) -> None:
    """Reject missing, empty or duplicate release sections."""
    (release_root / "CHANGELOG.md").write_text(content)
    with pytest.raises(ValueError, match="changelog section"):
        release_notes(release_root, "release/v0.3.0")
