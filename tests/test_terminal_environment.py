"""Project Python environments are scoped to newly started terminal processes."""

import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from cmf_dev_studio.api.terminal import shell_startup_command, terminal_environment
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage


def make_venv(root: Path) -> Path:
    executable = root / "bin" / "python"
    executable.parent.mkdir(parents=True)
    executable.touch()
    executable.chmod(0o755)
    (root / "pyvenv.cfg").write_text("version = 3.12.4\n")
    return executable


def test_terminal_uses_project_environment(tmp_path, monkeypatch):
    """Project Python takes priority without changing the parent environment."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    executable = make_venv(project.path / ".venv")
    monkeypatch.setenv("PATH", "/ide/bin:/usr/bin")
    monkeypatch.setenv("VIRTUAL_ENV", "/ide")
    monkeypatch.setenv("PYTHONHOME", "/ide")
    env = terminal_environment(project)
    assert env["PATH"] == f"{executable.parent}:/usr/bin"
    assert env["VIRTUAL_ENV"] == str(executable.parent.parent)
    assert "PYTHONHOME" not in env
    assert os.environ["PATH"] == "/ide/bin:/usr/bin"
    assert os.environ["VIRTUAL_ENV"] == "/ide"


def test_selected_environment_takes_priority(tmp_path):
    """An explicit interpreter wins over the automatically detected venv."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    make_venv(project.path / ".venv")
    selected = make_venv(tmp_path / "custom")
    project = replace(project, python_interpreter=str(selected))
    env = terminal_environment(project)
    assert env["PATH"].split(os.pathsep)[0] == str(selected.parent)
    assert env["VIRTUAL_ENV"] == str(selected.parent.parent)


def test_system_interpreter_is_not_a_virtual_environment(tmp_path, monkeypatch):
    """A selected system interpreter does not inherit the IDE's virtual environment."""
    project = ProjectManager(tmp_path).create("Demo", language=ProjectLanguage.PYTHON)
    executable = tmp_path / "bin" / "python"
    executable.parent.mkdir()
    executable.touch()
    executable.chmod(0o755)
    monkeypatch.setenv("VIRTUAL_ENV", "/ide")
    env = terminal_environment(replace(project, python_interpreter=str(executable)))
    assert env["PATH"].split(os.pathsep)[0] == str(executable.parent)
    assert "VIRTUAL_ENV" not in env


def test_unconfigured_and_non_python_projects_use_system_environment(
    tmp_path, monkeypatch
):
    """No interpreter or a non-Python project must not inherit the IDE venv."""
    manager = ProjectManager(tmp_path)
    project = manager.create("Demo", language=ProjectLanguage.PYTHON)
    monkeypatch.setenv("PATH", "/ide/bin:/usr/bin")
    monkeypatch.setenv("VIRTUAL_ENV", "/ide")
    monkeypatch.setenv("VIRTUAL_ENV_PROMPT", "ide")
    monkeypatch.setenv("PYTHONHOME", "/ide")
    expected = {**os.environ, "TERM": "xterm-256color", "PATH": "/usr/bin"}
    for key in ("VIRTUAL_ENV", "VIRTUAL_ENV_PROMPT", "PYTHONHOME"):
        expected.pop(key)
    assert terminal_environment(project) == expected
    make_venv(project.path / ".venv")
    monkeypatch.setattr("cmf_dev_studio.projects.jdk_environment.discover_jdks", list)
    for language in (ProjectLanguage.JAVA, ProjectLanguage.KOTLIN):
        assert terminal_environment(replace(project, language=language)) == expected
    missing = replace(project, python_interpreter="/missing/python")
    assert terminal_environment(missing) == expected


def test_terminal_uses_selected_jdk(tmp_path, monkeypatch):
    """Java and Kotlin use their own JDK without modifying the parent process."""
    manager = ProjectManager(tmp_path / "studio")
    homes = [tmp_path / "jdk17", tmp_path / "jdk21"]
    for home, version in zip(homes, ("17", "21"), strict=True):
        (home / "bin").mkdir(parents=True)
        for name in ("java", "javac"):
            executable = home / "bin" / name
            executable.touch()
            executable.chmod(0o755)
        (home / "release").write_text(f'JAVA_VERSION="{version}"\n')
    monkeypatch.setattr("cmf_dev_studio.projects.jdk_environment.discover_jdks", list)
    monkeypatch.setenv("JAVA_HOME", "/system/jdk")
    monkeypatch.setenv("PATH", "/ide/bin:/system/jdk/bin:/usr/bin")
    monkeypatch.setenv("VIRTUAL_ENV", "/ide")
    for language, home in zip(("java", "kotlin"), homes, strict=True):
        project = manager.create(language, language=language)
        project = manager.update_jdk(project.id, str(home))
        env = terminal_environment(project)
        assert env["JAVA_HOME"] == str(home)
        assert env["PATH"] == f"{home}/bin:/system/jdk/bin:/usr/bin"
        assert "VIRTUAL_ENV" not in env
    assert os.environ["JAVA_HOME"] == "/system/jdk"
    assert os.environ["PATH"] == "/ide/bin:/system/jdk/bin:/usr/bin"


def test_terminal_uses_detected_jdk(tmp_path, monkeypatch):
    """Automatic selection also configures the terminal."""
    home = tmp_path / "jdk"
    monkeypatch.setattr(
        "cmf_dev_studio.projects.jdk_environment.discover_jdks",
        lambda: [{"path": str(home), "version": "21"}],
    )
    project = ProjectManager(tmp_path / "studio").create("Demo", language="java")
    env = terminal_environment(project)
    assert env["JAVA_HOME"] == str(home)
    assert env["PATH"].split(os.pathsep)[0] == str(home / "bin")


@pytest.mark.parametrize("shell_name", ["bash", "zsh"])
@pytest.mark.parametrize("language", ["java", "kotlin", "python"])
def test_shell_startup_preserves_project_environment(
    tmp_path, monkeypatch, shell_name, language
):
    """Real interactive startup must not override the selected environment."""
    shell = shutil.which(shell_name)
    if not shell:
        pytest.skip(f"{shell_name} is not installed")
    home = tmp_path / "user home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ZDOTDIR", raising=False)
    project = ProjectManager(tmp_path / "studio").create("Demo", language=language)
    selected = tmp_path / "selected environment"
    if language == "python":
        make_venv(selected)
        project = replace(project, python_interpreter=str(selected / "bin" / "python"))
        variable = "VIRTUAL_ENV"
    else:
        (selected / "bin").mkdir(parents=True)
        for name in ("java", "javac"):
            executable = selected / "bin" / name
            executable.touch()
            executable.chmod(0o755)
        (selected / "release").write_text('JAVA_VERSION="17"\n')
        project = replace(project, jdk_home=str(selected))
        variable = "JAVA_HOME"
    rc = home / (".bashrc" if shell_name == "bash" else ".zshrc")
    content = (
        f"export {variable}=/system/default\n"
        "export PATH=/system/default/bin:$PATH\n"
        "export USER_RC_LOADED=yes\n"
    )
    rc.write_text(content)
    startup = tmp_path / "startup"
    startup.mkdir()
    env = terminal_environment(project)
    args = shell_startup_command(shell, env, project, startup)
    result = subprocess.run(
        [
            *args,
            "-c",
            f'printf "%s\\n" "${variable}" "${{PATH%%:*}}" "$USER_RC_LOADED"',
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert result.stdout.splitlines()[-3:] == [
        str(selected),
        str(selected / "bin"),
        "yes",
    ]
    assert rc.read_text() == content
