"""Validate release metadata and extract the matching changelog section."""

import argparse
import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10; tomli is a pytest dependency.
    import tomli as tomllib


def release_notes(root: Path, branch: str) -> tuple[str, str]:
    """Return the validated version and release notes without changing files."""
    match = re.fullmatch(
        r"release/v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", branch
    )
    if not match:
        raise ValueError("Expected release/vX.Y.Z")
    version = ".".join(match.groups())
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    studio = [p for p in lock["package"] if p["name"] == "cmf-dev-studio"]
    frontend = json.loads((root / "frontend/package.json").read_text(encoding="utf-8"))
    npm_lock = json.loads(
        (root / "frontend/package-lock.json").read_text(encoding="utf-8")
    )
    versions = {
        "pyproject.toml": project["project"].get("version"),
        "uv.lock": studio[0].get("version") if len(studio) == 1 else None,
        "frontend/package.json": frontend.get("version"),
        "frontend/package-lock.json": npm_lock.get("version"),
        "frontend/package-lock.json root": npm_lock.get("packages", {})
        .get("", {})
        .get("version"),
    }
    for filename, actual in versions.items():
        if actual != version:
            raise ValueError(f"{filename}: expected {version}, found {actual}")
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = list(re.finditer(r"(?m)^## (?!#)(.*)$", changelog))
    matching = [
        i
        for i, heading in enumerate(headings)
        if re.fullmatch(
            rf"\[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}", heading.group(1)
        )
    ]
    if len(matching) != 1:
        raise ValueError(f"Expected one dated changelog section for {version}")
    index = matching[0]
    end = headings[index + 1].start() if index + 1 < len(headings) else len(changelog)
    notes = changelog[headings[index].end() : end].strip()
    notes = re.split(r"(?m)^\[[^\]]+\]:", notes, maxsplit=1)[0].strip()
    if not notes:
        raise ValueError(f"Empty changelog section for {version}")
    return version, notes


def main() -> None:
    """Write validated notes for the GitHub CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("branch")
    parser.add_argument("--notes", type=Path, required=True)
    args = parser.parse_args()
    version, notes = release_notes(Path.cwd(), args.branch)
    args.notes.write_text(notes + "\n", encoding="utf-8")
    print(version)


if __name__ == "__main__":
    main()
