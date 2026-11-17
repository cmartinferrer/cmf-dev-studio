"""Native test commands, executed only after proposal approval by the caller."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass(frozen=True)
class RunnerSpec:
    name: str
    command: tuple[str, ...]
    timeout: int = 300
    jdk_home: str | None = None
    jdk_version: str | None = None


class UnsupportedRunner(ValueError):
    pass


def select_runner(workspace: Path, python: str | None = None) -> RunnerSpec:
    paths = {
        p.relative_to(workspace).as_posix() for p in workspace.rglob("*") if p.is_file()
    }
    if "pom.xml" in paths:
        if not any(
            p.startswith("src/test/") and p.endswith((".java", ".kt")) for p in paths
        ):
            raise UnsupportedRunner("Maven project has no test sources")
        command = ("sh", "./mvnw") if "mvnw" in paths else ("mvn",)
        return RunnerSpec("maven", (*command, "-B", "test", "-DfailIfNoTests=true"))
    if {"build.gradle.kts", "build.gradle"} & paths:
        if not any(
            p.startswith("src/test/") and p.endswith((".java", ".kt")) for p in paths
        ):
            raise UnsupportedRunner("Gradle project has no test sources")
        command = ("sh", "./gradlew") if "gradlew" in paths else ("gradle",)
        return RunnerSpec(
            "gradle", (*command, "test", "--console=plain", "--no-daemon")
        )
    if any(p.endswith(".py") for p in paths):
        command = ["uv", "run", "--isolated", "--no-python-downloads"]
        if python:
            command.extend(("--python", python))
        if "pyproject.toml" not in paths:
            command.append("--no-project")
        if "requirements.txt" in paths:
            command.extend(("--with-requirements", "requirements.txt"))
        command.extend(("--with", "pytest", "--", "python", "-m", "pytest", "-q"))
        return RunnerSpec("pytest", tuple(command))
    raise UnsupportedRunner(
        "No supported test runner (Python/pytest, Java/Maven or Java/Kotlin/Gradle)"
    )


def execute_runner(
    workspace: Path, spec: RunnerSpec, *, in_place: bool = False
) -> tuple[bool, str]:
    # A disposable copy protects against ordinary build artifacts, not hostile code.
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        in {
            "PATH",
            "HOME",
            "USER",
            "LOGNAME",
            "LANG",
            "LC_ALL",
            "JAVA_HOME",
            "GRADLE_USER_HOME",
            "SYSTEMROOT",
            "TMPDIR",
            "XDG_CACHE_HOME",
        }
    }
    if spec.jdk_home:
        bin_dir = str(Path(spec.jdk_home) / "bin")
        paths = env.get("PATH", os.defpath).split(os.pathsep)
        env["JAVA_HOME"] = spec.jdk_home
        env["PATH"] = os.pathsep.join(
            [bin_dir, *(path for path in paths if path != bin_dir)]
        )
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    required = {
        "./mvnw": (".mvn/wrapper/maven-wrapper.properties",),
        "./gradlew": (
            "gradle/wrapper/gradle-wrapper.properties",
            "gradle/wrapper/gradle-wrapper.jar",
        ),
    }
    if spec.command[:1] == ("sh",) and len(spec.command) > 1:
        missing = [
            name
            for name in required.get(spec.command[1], ())
            if not (workspace / name).is_file()
        ]
        if missing:
            return False, (
                f"Runner: {spec.name} (infrastructure_error): Incomplete wrapper. "
                f"Missing: {', '.join(missing)}. Restore these files and start a new request."
            )
    if spec.command[0] in ("mvn", "gradle") and not shutil.which(
        spec.command[0], path=env.get("PATH", os.defpath)
    ):
        tool = "Maven" if spec.name == "maven" else "Gradle"
        wrapper = "mvnw" if spec.name == "maven" else "gradlew"
        return False, (
            f"Runner: {spec.name} (infrastructure_error): {tool} is not available. "
            f"Add a complete {wrapper} wrapper to the project or make {tool} "
            "available on the IDE backend PATH before retrying."
        )
    try:
        with TemporaryDirectory(prefix="cmf-test-") as directory:
            root = workspace if in_place else Path(directory) / "project"
            if not in_place:
                shutil.copytree(workspace, root)
            with subprocess.Popen(
                spec.command,
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            ) as process:
                try:
                    output, _ = process.communicate(timeout=spec.timeout)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.communicate()
                    return (
                        False,
                        f"Runner: {spec.name} (infrastructure_error) timed out after {spec.timeout} seconds",
                    )
                code = process.returncode
        classification = (
            "infrastructure_error"
            if code in (125, 126, 127)
            or (spec.name == "pytest" and code in (3, 4))
            or (
                spec.name == "pytest"
                and code == 2
                and any(
                    line.startswith(("error:", "  ×")) for line in output.splitlines()
                )
            )
            else "test_result"
        )
        return (
            code == 0,
            f"Runner: {spec.name} (exit {code}; {classification})\n{output[-16000:]}",
        )
    except OSError as exc:
        return False, f"Runner: {spec.name} (infrastructure_error): {exc}"
