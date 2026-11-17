"""Resolve conventional JVM entry points for explicit editor execution."""

import re
from pathlib import Path

from cmf_dev_studio.projects.editor import safe_path
from cmf_dev_studio.projects.jdk_environment import environment_info
from cmf_dev_studio.projects.models import Project


def jvm_run_command(project: Project, path: str, startup_dir: Path) -> list[str]:
    """Build a command for a main class or a conventional test source."""
    target = safe_path(project.path, path)
    if project.language.value not in ("java", "kotlin"):
        raise ValueError("Select a Java or Kotlin project")
    if target.suffix not in (".java", ".kt"):
        raise ValueError("Select a Java or Kotlin source file")
    jdk = environment_info(project)["current"]
    if not jdk:
        raise ValueError("Select an available JDK in the status bar")
    parts = Path(path).parts
    if (
        len(parts) < 4
        or parts[0] != "src"
        or parts[1] not in ("main", "test")
        or parts[2] not in ("java", "kotlin")
    ):
        raise ValueError("Run supports conventional src/main and src/test sources")
    source = target.read_text(encoding="utf-8")
    package = re.search(r"(?m)^\s*package\s+([\w.]+)", source)
    name = target.stem
    if not re.fullmatch(r"[A-Za-z_$][\w$]*", name):
        raise ValueError("Unsupported JVM class name")
    is_test = parts[1] == "test"
    if is_test:
        if not re.search(r"\bclass\s+" + re.escape(name) + r"\b", source):
            raise ValueError("Select a test class matching its filename")
    elif target.suffix == ".java":
        if not re.search(r"\bstatic\s+void\s+main\s*\(", source):
            raise ValueError("This file has no supported main method")
    else:
        if not re.search(r"(?m)^\s*fun\s+main\s*\(", source):
            raise ValueError("This file has no supported top-level main function")
        name += "Kt"
    qualified = f"{package.group(1)}.{name}" if package else name
    root = project.path
    if (root / "pom.xml").is_file():
        command = ["sh", "./mvnw"] if (root / "mvnw").is_file() else ["mvn"]
        if is_test:
            return [
                *command,
                "-B",
                "test",
                f"-Dtest={qualified}",
                "-DfailIfNoTests=true",
            ]
        return [
            *command,
            "-B",
            "compile",
            "org.codehaus.mojo:exec-maven-plugin:3.5.0:exec",
            f"-Dexec.executable={Path(jdk['path']) / 'bin' / 'java'}",
            "-Dexec.args=-classpath %classpath " + qualified,
        ]
    if any((root / file).is_file() for file in ("build.gradle", "build.gradle.kts")):
        command = ["sh", "./gradlew"] if (root / "gradlew").is_file() else ["gradle"]
        if is_test:
            return [
                *command,
                "test",
                "--tests",
                qualified,
                "--console=plain",
                "--no-daemon",
            ]
        init = startup_dir / "cmf-run.gradle"
        init.write_text(
            """gradle.projectsEvaluated {
    def p = gradle.rootProject
    p.tasks.register('cmfEditorRun', JavaExec) {
        dependsOn p.tasks.named('classes')
        classpath = p.extensions.getByName('sourceSets').getByName('main').runtimeClasspath
        mainClass.set(p.providers.gradleProperty('cmfEditorMain'))
        standardInput = System.in
    }
}
""",
            encoding="utf-8",
        )
        return [
            *command,
            "--init-script",
            str(init),
            "cmfEditorRun",
            f"-PcmfEditorMain={qualified}",
            "--console=plain",
            "--no-daemon",
        ]
    raise ValueError("Run requires a Maven or Gradle project")
