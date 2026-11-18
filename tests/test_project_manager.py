"""Project registry tests; no Gemini or Docker required."""

import pytest

from cmf_dev_studio.projects import ProjectLanguage, ProjectManager


def test_create_local_project_and_reload(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("My Calculator", "Example project", location=tmp_path)
    assert project.path.is_dir()
    assert project.description == "Example project"
    assert ProjectManager(tmp_path / "studio").get(project.id) == project


def test_same_name_creates_distinct_workspaces(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    first = manager.create("Calculator", location=tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    second = manager.create("Calculator", location=other)
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
def test_invalid_project_names_are_rejected(tmp_path, name):
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError):
        manager.create(name, location=tmp_path)
    assert not (tmp_path / "Calculator").exists()


def test_missing_existing_path_is_rejected(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError, match="not found"):
        manager.register_existing(tmp_path / "missing")


def test_studio_data_dir_cannot_be_registered(tmp_path):
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError, match="own data"):
        manager.register_existing(manager.data_dir)


def test_unknown_id_returns_none(tmp_path):
    assert ProjectManager(tmp_path / "studio").get("not-found") is None


@pytest.mark.parametrize(
    "language", [ProjectLanguage.PYTHON, ProjectLanguage.JAVA, ProjectLanguage.KOTLIN]
)
def test_create_project_with_language(tmp_path, language):
    """New projects preserve their configured programming language."""
    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("Calculator", language=language, location=tmp_path)
    assert project.language is language
    assert manager.get(project.id).language is language


def test_project_language_persists_after_reload(tmp_path):
    """Project language survives restarting the project manager."""
    data_dir = tmp_path / "studio"
    project = ProjectManager(data_dir).create(
        "Calculator", language=ProjectLanguage.JAVA, location=tmp_path
    )
    assert ProjectManager(data_dir).get(project.id).language is ProjectLanguage.JAVA


def test_project_language_defaults_to_auto(tmp_path):
    """Projects without an explicit language retain automatic detection."""
    assert (
        ProjectManager(tmp_path / "studio")
        .create("Calculator", location=tmp_path)
        .language
        is ProjectLanguage.AUTO
    )


def test_existing_project_defaults_to_auto(tmp_path):
    """Registered repositories retain automatic language detection."""
    repository = tmp_path / "repository"
    repository.mkdir()
    assert (
        ProjectManager(tmp_path / "studio").register_existing(repository).language
        is ProjectLanguage.AUTO
    )


def test_invalid_language_does_not_create_workspace(tmp_path):
    """Unsupported languages are rejected without leaving orphan workspaces."""
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(ValueError):
        manager.create("Calculator", language="unsupported", location=tmp_path)
    assert manager.list_projects() == []
    assert not (tmp_path / "Calculator").exists()


@pytest.mark.parametrize("existing", [False, True])
def test_update_language_preserves_project_and_files(tmp_path, existing):
    """Changing language persists only registry metadata for newly created and registered projects."""
    from dataclasses import replace

    manager = ProjectManager(tmp_path / "studio")
    if existing:
        repository = tmp_path / "repo"
        repository.mkdir()
        project = manager.register_existing(repository)
    else:
        project = manager.create(
            "Demo", language=ProjectLanguage.JAVA, location=tmp_path
        )
    source = project.path / "source.txt"
    source.write_text("unchanged\n")
    for language in ProjectLanguage:
        expected = replace(project, language=language)
        assert manager.update_language(project.id, language) == expected
        assert ProjectManager(manager.data_dir).get(project.id) == expected
    assert source.read_text() == "unchanged\n"
    assert list(project.path.iterdir()) == [source]
    assert manager.update_language("missing", ProjectLanguage.JAVA) is None
    with pytest.raises(ValueError):
        manager.update_language(project.id, "invalid")


def test_local_project_lifecycle(tmp_path):
    """Removing a project preserves files; explicit deletion removes them."""
    manager = ProjectManager(tmp_path / "studio")
    project = manager.create("Local", location=tmp_path)
    assert project.path == tmp_path / "Local"
    (project.path / "main.py").write_text("hello")
    assert manager.delete(project.id)
    assert (project.path / "main.py").exists()
    reopened = manager.register_existing(project.path)
    assert manager.delete(reopened.id, from_disk=True)
    assert not project.path.exists()


def test_location_required_and_internal_directory_protected(tmp_path):
    """Projects must live outside Studio's internal storage."""
    manager = ProjectManager(tmp_path / "studio")
    with pytest.raises(TypeError):
        manager.create("Demo")
    with pytest.raises(ValueError, match="own data"):
        manager.create("Demo", location=manager.data_dir)
    assert not (manager.data_dir / "workspaces").exists()
    assert manager.list_projects() == []
