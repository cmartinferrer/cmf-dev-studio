"""Project registry tests; no Gemini or Docker required."""

import sqlite3

import pytest

from cmf_dev_studio.projects import ProjectKind, ProjectLanguage, ProjectManager


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


@pytest.mark.parametrize("language", [ProjectLanguage.PYTHON, ProjectLanguage.JAVA, ProjectLanguage.KOTLIN])
def test_create_project_with_language(tmp_path, language):
    """Managed projects preserve their configured programming language."""
    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("Calculator", language=language)
    assert project.language is language
    assert manager.get(project.id).language is language


def test_project_language_persists_after_reload(tmp_path):
    """Project language survives restarting the project manager."""
    data_dir = tmp_path / "studio"
    project = ProjectManager(data_dir).create("Calculator", language=ProjectLanguage.JAVA)
    assert ProjectManager(data_dir).get(project.id).language is ProjectLanguage.JAVA


def test_project_language_defaults_to_auto(tmp_path):
    """Projects without an explicit language retain automatic detection."""
    assert ProjectManager(tmp_path / "studio").create("Calculator").language is ProjectLanguage.AUTO


def test_existing_project_defaults_to_auto(tmp_path):
    """Registered repositories retain automatic language detection."""
    repository = tmp_path / "repository"
    repository.mkdir()
    assert ProjectManager(tmp_path / "studio").register_existing(repository).language is ProjectLanguage.AUTO


def test_migrate_legacy_project_database(tmp_path):
    """Legacy projects survive schema migration and default to auto."""
    manager = ProjectManager(tmp_path / "studio")
    original = manager.create("Legacy")
    with sqlite3.connect(manager.db_path) as db:
        db.execute("ALTER TABLE projects DROP COLUMN language")
    migrated = ProjectManager(manager.data_dir)
    assert migrated.get(original.id) == original
    assert migrated.create("New", language=ProjectLanguage.KOTLIN).language is ProjectLanguage.KOTLIN
    assert ProjectManager(manager.data_dir).get(original.id) == original


def test_invalid_language_does_not_create_workspace(tmp_path):
    """Unsupported languages are rejected without leaving orphan workspaces."""
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError):
        manager.create("Calculator", language="unsupported")
    assert manager.list_projects() == []
    assert list(manager.managed_dir.iterdir()) == []
