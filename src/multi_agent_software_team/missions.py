"""Persistent, project-scoped mission execution (no project file writes)."""

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from multi_agent_software_team.projects.intelligence import prepare_context, format_context
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable
from uuid import uuid4

from multi_agent_software_team.events import ExecutionEvent
from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.projects import ProjectManager


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionService:
    """Submit one mission per project, retain events and generated artifacts in SQLite."""

    def __init__(self, manager: ProjectManager, execute: Callable[[Mission, Callable[[ExecutionEvent], None]], Mission] | None = None):
        self.manager = manager
        self._execute = execute or self._execute_real
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="studio-mission")
        self._lock = Lock()
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS mission_runs (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, description TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                result TEXT, error TEXT NOT NULL DEFAULT ''
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS mission_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL, payload TEXT NOT NULL
            )""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_active_mission_per_project
                ON mission_runs(project_id) WHERE status IN ('queued', 'running')""")

    def _db(self):
        connection = sqlite3.connect(self.manager.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _execute_real(mission: Mission, on_event: Callable[[ExecutionEvent], None]) -> Mission:
        from dotenv import load_dotenv
        from multi_agent_software_team.llm.gemini import GeminiClient
        from multi_agent_software_team.orchestrator import Orchestrator
        from multi_agent_software_team.runner.docker import DockerTestRunner
        load_dotenv()
        return Orchestrator(llm=GeminiClient(), runner=DockerTestRunner(), on_event=on_event).run(mission)

    def recover_interrupted(self) -> int:
        """Mark unfinished runs from a previous server process as failed.

        Call only during API initialization, before accepting new submissions.
        This does not resume work or terminate an external worker.
        """
        with self._db() as db:
            cursor = db.execute(
                """UPDATE mission_runs SET status='failed', updated_at=?,
                   error='Mission interrupted by server restart; start a new mission to retry.'
                   WHERE status IN ('queued', 'running')""",
                (_now(),),
            )
            return cursor.rowcount

    def submit(self, project_id: str, description: str, context_paths: list[str] | None = None, context_digest: str | None = None) -> dict:
        if self.manager.get(project_id) is None:
            raise KeyError("Project not found")
        description = description.strip()
        if not description or len(description) > 10000:
            raise ValueError("Mission description must be between 1 and 10000 characters")
        project = self.manager.get(project_id)
        # Read only files explicitly approved by the user, before queueing.
        # Context is passed in-memory to the worker; never persisted in mission_runs.
        context = prepare_context(project.path, context_paths or [])
        if context_paths and (not context_digest or context_digest != context['digest']):
            raise ValueError('Repository files changed or were not approved; review context again')
        execution_description = description + format_context(context)
        run_id, now = str(uuid4()), _now()
        with self._lock:
            try:
                with self._db() as db:
                    db.execute("INSERT INTO mission_runs (id,project_id,description,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                               (run_id, project_id, description, "queued", now, now))
            except sqlite3.IntegrityError as exc:
                raise ValueError("A mission is already active for this project") from exc
        self._pool.submit(self._run, run_id, execution_description)
        return self.get(run_id)

    def _run(self, run_id: str, description: str) -> None:
        with self._db() as db:
            db.execute("UPDATE mission_runs SET status='running',updated_at=? WHERE id=?", (_now(), run_id))

        def record(event: ExecutionEvent) -> None:
            payload = asdict(event)
            payload["type"] = event.type.value
            with self._db() as db:
                db.execute("INSERT INTO mission_events(run_id,occurred_at,payload) VALUES (?,?,?)",
                           (run_id, _now(), json.dumps(payload)))

        try:
            result = self._execute(Mission(description=description), record)
            serialized = {
                "requirements": result.requirements, "code": result.code,
                "tests": result.tests, "feedback": result.feedback,
                "attempts": result.attempts,
                "history": [{**asdict(a), "status": a.status.value} for a in result.history],
            }
            status = "completed" if result.status is MissionStatus.COMPLETED else "failed"
            with self._db() as db:
                db.execute("UPDATE mission_runs SET status=?,updated_at=?,result=? WHERE id=?",
                           (status, _now(), json.dumps(serialized), run_id))
        except Exception as exc:
            with self._db() as db:
                db.execute("UPDATE mission_runs SET status='failed',updated_at=?,error=? WHERE id=?",
                           (_now(), str(exc), run_id))

    def get(self, run_id: str) -> dict | None:
        with self._db() as db:
            row = db.execute("SELECT * FROM mission_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["result"] = json.loads(value["result"]) if value["result"] else None
        return value

    def list_for_project(self, project_id: str) -> list[dict]:
        with self._db() as db:
            ids = [r[0] for r in db.execute("SELECT id FROM mission_runs WHERE project_id=? ORDER BY created_at DESC", (project_id,))]
        return [self.get(run_id) for run_id in ids]

    def events(self, run_id: str, after_id: int = 0) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT * FROM mission_events WHERE run_id=? AND id>? ORDER BY id", (run_id, after_id)).fetchall()
        return [{"id": r["id"], "occurred_at": r["occurred_at"], **json.loads(r["payload"])} for r in rows]
