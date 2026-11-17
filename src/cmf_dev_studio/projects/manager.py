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

            for column in ("python_interpreter", "python_version"):
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
    ) -> Project:
        """Create an empty managed workspace, never replacing an existing folder."""
        name = self._validate_name(name)
        # IDs avoid collisions even for projects with identical display names.
        project_id = uuid4().hex
        path = self.managed_dir / project_id
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
        if resolved == self.data_dir or self.data_dir in resolved.parents:
            raise ValueError("Cannot register the studio's own data directory")
        name = self._validate_name(name if name is not None else resolved.name)
        return self._insert(name, resolved, ProjectKind.EXISTING, description)

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

    def delete(self, project_id: str) -> bool:
        """Unregister external projects; remove only owned managed directories."""
        project = self.get(project_id)
        if project is None:
            return False
        if project.kind == ProjectKind.MANAGED:
            root = self.managed_dir.resolve()
            path = project.path
            if (
                self.managed_dir.is_symlink()
                or path.parent != root
                or path.is_symlink()
                or path.resolve() != path
            ):
                raise ValueError("Unsafe managed workspace path")
            if path.exists():
                shutil.rmtree(path)
        with self._connect() as db:
            db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return True
