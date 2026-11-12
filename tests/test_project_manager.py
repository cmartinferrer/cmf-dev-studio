"""Project registry tests; no Gemini or Docker required."""

import sqlite3

import pytest

from cmf_dev_studio.projects import ProjectKind, ProjectManager


def test_create_managed_workspace_and_reload(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("My Calculator", "Example project")
    assert project.kind is ProjectKind.MANAGED
    assert not project.read_only
    assert project.path.is_dir()
    assert project.description == "Example project"
    assert ProjectManager(tmp_path / "studio").get(project.id) == project


def test_same_name_creates_distinct_workspaces(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    first = manager.create("Calculator")
    second = manager.create("Calculator")
    assert first.id != second.id
    assert first.path != second.path
    assert len(manager.list_projects()) == 2


def test_register_existing_does_not_modify_files(tmp_path):
    repository = tmp_path / "source"
    repository.mkdir()
    file = repository / "main.py"
    file.write_text("print('hello')\n")
    manager = ProjectManager(tmp_path / "studio")
    project = manager.register_existing(repository)
    assert project.kind is ProjectKind.EXISTING
    assert project.read_only
    assert project.path == repository.resolve()
    assert file.read_text() == "print('hello')\n"
    assert set(repository.iterdir()) == {file}


def test_duplicate_existing_path_is_rejected(tmp_path):
    repository = tmp_path / "source"
    repository.mkdir()
    manager = ProjectManager(tmp_path / "studio")
    manager.register_existing(repository)
    with pytest.raises(ValueError, match="already registered"):
        manager.register_existing(repository)


@pytest.mark.parametrize("name", ["", "  ", "../oops", "a/b", ".", "..", "x" * 81])
def test_invalid_managed_names_are_rejected(tmp_path, name):
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError):
        manager.create(name)
    assert list(manager.managed_dir.iterdir()) == []


def test_missing_existing_path_is_rejected(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError, match="not found"):
        manager.register_existing(tmp_path / "missing")


def test_studio_data_dir_cannot_be_registered(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError, match="own data"):
        manager.register_existing(manager.managed_dir)


def test_unknown_id_returns_none(tmp_path):
    assert ProjectManager(tmp_path / "studio").get("not-found") is None
