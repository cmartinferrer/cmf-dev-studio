"""SQLite-backed registry for new and existing local code projects.

No agents are invoked and no existing project files are changed here.
"""

import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import Project, ProjectKind, ProjectLanguage

_NAME_PATTERN = re.compile(r"^[\w][\w .-]{0,79}$", re.UNICODE)


class ProjectManager:
    def __init__(self, data_dir: Path | str):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.managed_dir = self.data_dir / "workspaces"
        self.db_path = self.data_dir / "projects.sqlite3"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.managed_dir.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL CHECK(kind IN ('managed', 'existing')),
                description TEXT NOT NULL,
                created_at TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'auto'
            )""")
            columns = {row["name"] for row in db.execute("PRAGMA table_info(projects)")}
            if "language" not in columns:
                db.execute(
                    "ALTER TABLE projects ADD COLUMN language TEXT NOT NULL DEFAULT 'auto'"
                )

            for column in ("python_interpreter", "python_version", "jdk_home"):
                if column not in columns:
                    db.execute(f"ALTER TABLE projects ADD COLUMN {column} TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _validate_name(name: str) -> str:
        name = name.strip()
        if name in {".", ".."} or not _NAME_PATTERN.fullmatch(name):
            raise ValueError(
                "Project name must be 1-80 characters (letters, numbers, spaces, _, . or -)"
            )
        return name

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            path=Path(row["path"]),
            kind=ProjectKind(row["kind"]),
            description=row["description"],
            created_at=row["created_at"],
            language=ProjectLanguage(row["language"]),
            python_interpreter=row["python_interpreter"],
            python_version=row["python_version"],
            jdk_home=row["jdk_home"],
        )

    def _insert(
        self,
        name: str,
        path: Path,
        kind: ProjectKind,
        description: str,
        language: ProjectLanguage = ProjectLanguage.AUTO,
    ) -> Project:
        project = Project(
            id=str(uuid4()),
            name=name,
            path=path,
            kind=kind,
            description=description,
            language=ProjectLanguage(language),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._connect() as db:
            try:
                db.execute(
                    "INSERT INTO projects (id, name, path, kind, description, created_at, language) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        project.id,
                        project.name,
                        str(project.path),
                        project.kind.value,
                        project.description,
                        project.created_at,
                        project.language.value,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Project path is already registered: {path}") from exc
        return project

    def create(
        self,
        name: str,
        description: str = "",
        language: ProjectLanguage = ProjectLanguage.AUTO,
        location: str | Path | None = None,
    ) -> Project:
        """Create an empty managed workspace, never replacing an existing folder."""
        name = self._validate_name(name)
        # IDs avoid collisions even for projects with identical display names.
        project_id = uuid4().hex
        path = (
            self.managed_dir / project_id
            if location is None
            else Path(location).expanduser().resolve(strict=True) / name
        )
        if location is not None:
            self._validate_root(path)
        path.mkdir(exist_ok=False)
        try:
            return self._insert(
                name, path.resolve(), ProjectKind.MANAGED, description, language
            )
        except Exception:
            path.rmdir()  # Roll back only the new, still-empty directory.
            raise

    def register_existing(
        self, path: Path | str, name: str | None = None, description: str = ""
    ) -> Project:
        """Register a real directory without reading or writing its contents."""
        supplied = Path(path).expanduser()
        if not supplied.is_dir():
            raise ValueError(f"Existing project directory not found: {supplied}")
        resolved = supplied.resolve(strict=True)
        self._validate_root(resolved)
        return self._insert(resolved.name, resolved, ProjectKind.EXISTING, "")

    def get(self, project_id: str) -> Project | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def update_language(
        self, project_id: str, language: ProjectLanguage
    ) -> Project | None:
        """Update registry metadata without touching the project's files."""
        language = ProjectLanguage(language)
        with self._connect() as db:
            db.execute(
                "UPDATE projects SET language = ? WHERE id = ?",
                (language.value, project_id),
            )
            row = db.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def update_python_interpreter(
        self, project_id: str, path: str | None, version: str | None
    ) -> Project | None:
        """Persist interpreter metadata without modifying project files."""
        with self._connect() as db:
            db.execute(
                "UPDATE projects SET python_interpreter=?, python_version=? WHERE id=?",
                (path, version, project_id),
            )
        return self.get(project_id)

    def update_jdk(self, project_id: str, home: str | None) -> Project | None:
        """Persist the selected JDK without modifying project files."""
        with self._connect() as db:
            db.execute("UPDATE projects SET jdk_home=? WHERE id=?", (home, project_id))
        return self.get(project_id)

    def list_projects(self) -> list[Project]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM projects ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def rename(self, project_id: str, name: str) -> Project | None:
        """Rename display metadata without moving the workspace."""
        name = self._validate_name(name)
        with self._connect() as db:
            db.execute("UPDATE projects SET name=? WHERE id=?", (name, project_id))
        return self.get(project_id)

    def _validate_root(self, path: Path) -> None:
        if path == Path.home().resolve() or path == Path(path.anchor):
            raise ValueError("Choose a dedicated project directory")
        if (
            path == self.data_dir
            or path in self.data_dir.parents
            or self.data_dir in path.parents
        ) and (path.parent != self.managed_dir or path.is_symlink()):
            raise ValueError("Cannot access the studio's own data directory")
        for project in self.list_projects():
            if path == project.path:
                raise ValueError("Project path is already registered")
            if path in project.path.parents or project.path in path.parents:
                raise ValueError("Project directories must not overlap")

    def delete(self, project_id: str, *, from_disk: bool = False) -> bool:
        """Remove registry metadata, optionally deleting the project directory."""
        project = self.get(project_id)
        if project is None:
            return False
        if from_disk:
            path = project.path
            if (
                path.is_symlink()
                or path.resolve() != path
                or path == Path.home().resolve()
                or path == Path(path.anchor)
            ):
                raise ValueError("Unsafe project directory")
            if (
                path == self.data_dir
                or path in self.data_dir.parents
                or (self.data_dir in path.parents and path.parent != self.managed_dir)
            ):
                raise ValueError("Cannot access the studio's own data directory")
            for other in self.list_projects():
                if other.id != project_id and (
                    path in other.path.parents or other.path in path.parents
                ):
                    raise ValueError("Project directories overlap")
            if path.exists():
                shutil.rmtree(path)
        with self._connect() as db:
            db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return True
