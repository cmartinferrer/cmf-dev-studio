"""Discover installed JDKs using release metadata, without executing binaries."""

import os
import re
import shutil
from pathlib import Path

from .models import Project, ProjectLanguage


def inspect_jdk(home: Path) -> dict[str, str] | None:
    """Require both Java and javac and readable version metadata."""
    try:
        home = home.resolve()
        suffix = ".exe" if os.name == "nt" else ""
        if not all(
            (home / "bin" / f"{name}{suffix}").is_file()
            and os.access(home / "bin" / f"{name}{suffix}", os.X_OK)
            for name in ("java", "javac")
        ):
            return None
        release = (home / "release").read_text(encoding="utf-8")
        match = re.search(r'^JAVA_VERSION="([^"\n]+)"$', release, re.MULTILINE)
        if not match:
            return None
        return {"path": str(home), "version": match.group(1)}
    except (OSError, UnicodeError, RuntimeError):
        return None


def discover_jdks() -> list[dict[str, str]]:
    """Inspect common system and user installation directories."""
    candidates = []
    if home := os.environ.get("JAVA_HOME"):
        candidates.append(Path(home))
    if java := shutil.which("javac"):
        candidates.append(Path(java).resolve().parent.parent)
    roots = [
        Path("/usr/lib/jvm"),
        Path("/Library/Java/JavaVirtualMachines"),
        Path.home() / ".sdkman/candidates/java",
        Path.home() / ".jdks",
        Path.home() / "Library/Java/JavaVirtualMachines",
    ]
    if os.name == "nt":
        roots.extend(
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / name
            for name in ("Java", "Eclipse Adoptium", "Microsoft")
        )
    for root in roots:
        try:
            for child in sorted(root.iterdir()):
                candidates.extend((child, child / "Contents/Home"))
        except OSError:
            continue
    found = {}
    for candidate in candidates:
        if info := inspect_jdk(candidate):
            found.setdefault(info["path"], info)
    return list(found.values())


def environment_info(project: Project) -> dict:
    """Prefer explicit selection, otherwise the first detected system JDK."""
    supported = project.language in (ProjectLanguage.JAVA, ProjectLanguage.KOTLIN) or (
        project.language == ProjectLanguage.AUTO
        and any(
            (project.path / name).is_file()
            for name in ("pom.xml", "build.gradle", "build.gradle.kts")
        )
    )
    available = discover_jdks() if supported else []
    selected = (
        inspect_jdk(Path(project.jdk_home)) if supported and project.jdk_home else None
    )
    if selected and selected not in available:
        available.append(selected)
    current = selected if project.jdk_home else (available[0] if available else None)
    return {
        "supported": supported,
        "current": current,
        "available": available,
        "source": "selected" if project.jdk_home else "detected" if current else "none",
    }
