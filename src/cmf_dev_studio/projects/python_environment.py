"""Inspect and explicitly create project Python environments without installing packages."""

import os
import re
import shutil
import subprocess
from pathlib import Path

from .models import Project, ProjectLanguage


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _config_version(root: Path) -> str | None:
    try:
        for line in (root / "pyvenv.cfg").read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() in {"version", "version_info"}:
                return value.strip() or None
    except (OSError, UnicodeError):
        return None
    return None


def environment_info(project: Project) -> dict:
    """Read metadata only; opening a repository never executes its interpreter."""
    root = project.path / ".venv"
    detected = _venv_python(root)
    supported = project.language == ProjectLanguage.PYTHON or (
        project.language == ProjectLanguage.AUTO
        and (
            root.exists()
            or any(
                (project.path / name).is_file()
                for name in (
                    "pyproject.toml",
                    "requirements.txt",
                    "uv.lock",
                    "setup.py",
                )
            )
            or any(project.path.glob("*.py"))
        )
    )
    selected = project.python_interpreter
    path = Path(selected) if selected else detected
    available = path.is_file() and os.access(path, os.X_OK)
    return {
        "supported": supported,
        "path": str(path) if selected or available else None,
        "version": (
            (project.python_version if selected else _config_version(root))
            if available
            else None
        ),
        "venv_exists": root.exists() or root.is_symlink(),
        "source": "selected" if selected else "detected" if available else "none",
        "available": available,
        "uv_available": shutil.which("uv") is not None,
    }


def select_interpreter(path: str) -> tuple[str, str]:
    """Probe only an explicitly approved executable; preserve venv symlink paths."""
    candidate = Path(path).expanduser()
    if (
        not candidate.is_absolute()
        or not candidate.is_file()
        or not os.access(candidate, os.X_OK)
    ):
        raise ValueError("Select an absolute path to an executable Python interpreter")
    result = subprocess.run(
        [str(candidate), "-I", "-S", "--version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    match = re.fullmatch(
        r"Python (\d+\.\d+\.\d+[^\s]*)", (result.stdout or result.stderr).strip()
    )
    if result.returncode or not match:
        raise ValueError("The selected executable did not report a Python version")
    return str(candidate), match.group(1)


def create_environment(project: Project) -> None:
    """Create an empty venv, never replace an existing directory or install packages."""
    root = project.path / ".venv"
    if root.exists() or root.is_symlink():
        raise ValueError(".venv already exists; it will not be replaced")
    uv = shutil.which("uv")
    if not uv:
        raise ValueError("uv is not installed or is not on PATH")
    root.mkdir(exist_ok=False)
    result = subprocess.run(
        [
            uv,
            "--no-config",
            "--no-python-downloads",
            "venv",
            "--allow-existing",
            str(root),
        ],
        cwd=project.path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise ValueError(
            result.stderr.strip()[-2000:] or "uv could not create the environment"
        )


def preparation_needed(project: Project, changes: list[dict]) -> bool:
    """Offer setup only for managed Python projects with a local environment."""
    info = environment_info(project)
    root = project.path / ".venv"
    if project.read_only or not info["supported"] or root.is_symlink():
        return False
    if project.python_interpreter and Path(project.python_interpreter) != _venv_python(
        root
    ):
        return False
    manifests = {"requirements.txt", "pyproject.toml", "uv.lock"}
    if project.language == ProjectLanguage.AUTO and not any(
        (project.path / name).is_file() for name in manifests
    ):
        return False
    return not info["available"] or any(c["path"] in manifests for c in changes)


def prepare_environment(project: Project) -> None:
    """Install declared dependencies only in the project's own .venv."""
    root = project.path / ".venv"
    python = _venv_python(root)
    if (
        project.read_only
        or not environment_info(project)["supported"]
        or root.is_symlink()
    ):
        raise ValueError("Preparation requires a managed Python project")
    if project.python_interpreter and Path(project.python_interpreter) != python:
        raise ValueError(
            "Select the project environment before installing dependencies"
        )
    uv = shutil.which("uv")
    if not uv:
        raise ValueError("uv is not installed or is not on PATH")
    if not root.exists():
        create_environment(project)
    if not python.is_file() or not (root / "pyvenv.cfg").is_file():
        raise ValueError("The project environment is incomplete")
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        in {
            "PATH",
            "HOME",
            "USER",
            "LANG",
            "LC_ALL",
            "SYSTEMROOT",
            "TMPDIR",
            "XDG_CACHE_HOME",
        }
    }
    env["UV_PROJECT_ENVIRONMENT"] = str(root)
    commands = []
    if (project.path / "pyproject.toml").is_file():
        command = [uv, "sync", "--no-python-downloads", "--project", str(project.path)]
        if (project.path / "uv.lock").is_file():
            command.append("--locked")
        commands.append(command)
    if (project.path / "requirements.txt").is_file():
        commands.append(
            [uv, "pip", "install", "--python", str(python), "-r", "requirements.txt"]
        )
    for command in commands:
        result = subprocess.run(
            command,
            cwd=project.path,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if result.returncode:
            raise ValueError(
                result.stderr.strip()[-4000:] or "Dependency installation failed"
            )
