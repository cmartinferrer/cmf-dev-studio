"""Explicitly approved builds of managed JVM projects."""

from dataclasses import replace

from cmf_dev_studio.project_runners import RunnerSpec, execute_runner
from cmf_dev_studio.projects.jdk_environment import environment_info
from cmf_dev_studio.projects.models import Project, ProjectLanguage


def preparation_spec(project: Project) -> RunnerSpec | None:
    """Select the build tool without requiring test sources."""
    if project.read_only or project.language == ProjectLanguage.PYTHON:
        return None
    root = project.path
    if (root / "pom.xml").is_file():
        command = ("sh", "./mvnw") if (root / "mvnw").is_file() else ("mvn",)
        return RunnerSpec("maven", (*command, "-B", "test"))
    if any((root / name).is_file() for name in ("build.gradle", "build.gradle.kts")):
        command = ("sh", "./gradlew") if (root / "gradlew").is_file() else ("gradle",)
        return RunnerSpec(
            "gradle", (*command, "classes", "test", "--console=plain", "--no-daemon")
        )
    return None


def prepare_jvm(project: Project) -> str:
    """Build in the actual project only after the caller obtains approval."""
    spec = preparation_spec(project)
    if spec is None:
        raise ValueError("Preparation requires a managed Maven or Gradle project")
    jdk = environment_info(project)["current"]
    if not jdk:
        raise ValueError("Select an available project JDK before preparing the project")
    spec = replace(spec, jdk_home=jdk["path"], jdk_version=jdk["version"])
    passed, output = execute_runner(project.path, spec, in_place=True)
    if not passed:
        raise ValueError(output)
    return output
