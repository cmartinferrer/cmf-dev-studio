"""Isolated, review-only repository workspaces and structured AI proposals."""
from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from threading import Thread
from uuid import uuid4

from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.models import ProjectLanguage
from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.contracts import Plan
from cmf_dev_studio.agents.developer import build_workspace_prompt
from cmf_dev_studio.project_runners import select_runner, execute_runner, UnsupportedRunner

EXCLUDED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.studio-data', '.runner-workspaces', '.pytest_cache', '.mypy_cache', '.tox', '.env', '.env.local', '.env.production', '.env.development', 'secrets', '.ssh'}
MAX_FILES = 350
MAX_BYTES = 3_000_000
MAX_FILE = 150_000

class WorkspaceError(ValueError):
    pass


def safe_path(value: str) -> Path:
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value or ':' in value:
        raise WorkspaceError('Invalid workspace file path')
    posix = PurePosixPath(value)
    if posix.is_absolute() or any(part in ('', '.', '..') or part.startswith('.') or part in EXCLUDED for part in posix.parts):
        raise WorkspaceError('Unsafe or hidden workspace file path')
    if posix.suffix.lower() not in {'.py', '.toml', '.md', '.txt', '.json', '.yaml', '.yml', '.ini', '.cfg', '.java', '.kt', '.kts', '.gradle', '.xml', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs', '.swift', '.html', '.css', '.sql', '.sh', '.properties'}:
        raise WorkspaceError('Unsupported file type')
    return Path(*posix.parts)


def digest(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None


def tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for file in sorted(root.rglob('*')):
        if file.is_symlink():
            raise WorkspaceError('Symlink found in isolated workspace')
        if file.is_file():
            h.update(file.relative_to(root).as_posix().encode('utf-8'))
            h.update(b'\0')
            h.update(file.read_bytes())
            h.update(b'\0')
    return h.hexdigest()


def snapshot(source: Path, target: Path) -> dict[str, bytes]:
    """Copy a bounded set of safe text files, without following symlinks."""
    copied: dict[str, bytes] = {}
    total = 0
    for root, dirs, files in os.walk(source, followlinks=False):
        base = Path(root)
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED and not d.startswith('.') and not (base / d).is_symlink())
        for filename in sorted(files):
            file = base / filename
            if filename in EXCLUDED or filename.startswith('.') or file.is_symlink() or not file.is_file():
                continue
            relative = file.relative_to(source).as_posix()
            try:
                safe_path(relative)
            except WorkspaceError:
                continue
            size = file.stat().st_size
            if size > MAX_FILE:
                continue
            if len(copied) >= MAX_FILES or total + size > MAX_BYTES:
                raise WorkspaceError('Repository exceeds safe workspace snapshot limits')
            raw = file.read_bytes()
            try:
                raw.decode('utf-8')
            except UnicodeDecodeError:
                continue
            dest = target / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
            copied[relative] = raw
            total += len(raw)
    return copied


def detect_languages(original: dict[str, bytes]) -> list[str]:
    """Identify technologies from paths, without sending file contents."""
    names = set(original)
    detected = []
    for name, condition in (
        ('Python', any(x.endswith('.py') for x in names)),
        ('Java', any(x.endswith('.java') for x in names) or 'pom.xml' in names),
        ('Kotlin', any(x.endswith(('.kt', '.kts')) for x in names)),
        ('JavaScript/TypeScript', any(x.endswith(('.js', '.jsx', '.ts', '.tsx')) for x in names)),
        ('Go', any(x.endswith('.go') for x in names)),
        ('Rust', any(x.endswith('.rs') for x in names)),
    ):
        if condition:
            detected.append(name)
    return detected


def project_task(task: str, language: ProjectLanguage) -> str:
    """Carry explicit project configuration to every agent, including repairs."""
    if language is ProjectLanguage.AUTO:
        return task
    name = {ProjectLanguage.PYTHON: 'Python', ProjectLanguage.JAVA: 'Java',
            ProjectLanguage.KOTLIN: 'Kotlin'}[language]
    return (f'PROJECT CONFIGURATION: Primary implementation language is {name}. '
            f'Use {name} for application code and its tests, with a compatible build '
            'and test runner. Supporting configuration and documentation may use other formats. '
            'Do not switch the primary language based on the task or an empty inventory. '
            f'\nUSER TASK:\n{task}')


def validate_operations(operations: object, original: dict[str, bytes], approved_paths: set[str]) -> None:
    if not isinstance(operations, list) or not 1 <= len(operations) <= 12:
        raise WorkspaceError('Expected 1-12 file operations; generate create operations for new files')
    seen: set[str] = set()
    for op in operations:
        if not isinstance(op, dict):
            raise WorkspaceError('Invalid operation object')
        path = op.get('path')
        safe_path(path)
        if path in seen:
            raise WorkspaceError(f'Duplicate operation: {path}')
        seen.add(path)
        action = op.get('action')
        existing = path in original
        if action == 'create' and existing:
            raise WorkspaceError(f'{path} already exists: use modify with approved contents')
        if action in ('modify', 'delete') and not existing:
            raise WorkspaceError(f'{path} does not exist: use create')
        if action in ('modify', 'delete') and path not in approved_paths:
            raise WorkspaceError(f'Permission required to read and modify {path}; approve it in Context')
        if action not in ('create', 'modify', 'delete'):
            raise WorkspaceError(f'Unsupported action: {action}')
        content = op.get('content', '')
        if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_FILE:
            raise WorkspaceError('Invalid or oversized file content')
        if action != 'delete' and '\x00' in content:
            raise WorkspaceError('NUL bytes are not allowed in source files')
        if action != 'delete' and path.endswith('.py'):
            try:
                ast.parse(content, filename=path)
            except SyntaxError as exc:
                raise WorkspaceError(f'Syntax error in {path}:{exc.lineno}: {exc.msg}') from exc


class WorkspaceService:
    def __init__(self, manager: ProjectManager):
        self.manager = manager
        self._test_approvals: dict[str, tuple[str, str]] = {}
        self.root = manager.data_dir / 'proposal-workspaces'
        self.root.mkdir(parents=True, exist_ok=True)
        self.baselines = manager.data_dir / 'proposal-baselines'
        self.baselines.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS workspace_proposals (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL, status TEXT NOT NULL,
                task TEXT NOT NULL, created_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT '',
                changes TEXT NOT NULL DEFAULT '[]')''')
            cols = {r[1] for r in db.execute('PRAGMA table_info(workspace_proposals)')}
            if 'test_output' not in cols:
                db.execute("ALTER TABLE workspace_proposals ADD COLUMN test_output TEXT NOT NULL DEFAULT ''")
            for name, definition in [('approved_paths', "TEXT NOT NULL DEFAULT '[]'"), ('plan', "TEXT NOT NULL DEFAULT '{}'"), ('attempts', 'INTEGER NOT NULL DEFAULT 0'), ('tested_digest', "TEXT NOT NULL DEFAULT ''"), ('agent_stage', "TEXT NOT NULL DEFAULT ''")]:
                if name not in cols:
                    db.execute(f'ALTER TABLE workspace_proposals ADD COLUMN {name} {definition}')

            db.execute("""CREATE TABLE IF NOT EXISTS proposal_events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT, proposal_id TEXT NOT NULL,
                kind TEXT NOT NULL, created_at TEXT NOT NULL, details TEXT NOT NULL)""")

    @staticmethod
    def _event(db, proposal_id, kind, **details):
        db.execute('INSERT INTO proposal_events(proposal_id,kind,created_at,details) VALUES (?,?,?,?)',
                   (proposal_id, kind, datetime.now(timezone.utc).isoformat(), json.dumps(details)))

    def defer(self, proposal_id: str, action: str) -> dict:
        with _APPLY_LOCK:
            row = self.get(proposal_id)
            if action == 'tests' and row['status'] in ('ready', 'test_failed'):
                kind = 'tests_skipped'
                self._test_approvals.pop(proposal_id, None)
            elif action == 'apply' and row['status'] == 'tested':
                kind = 'apply_deferred'
            else:
                raise WorkspaceError('Action cannot be deferred in the current state')
            with self._db() as db:
                self._event(db, proposal_id, kind)
            return self.get(proposal_id)

    def retry_generation(self, proposal_id: str, retry: bool = True, context_paths: list[str] | None = None, context_digest: str | None = None) -> dict:
        """Retry original context or explicitly approve a replacement against the baseline."""
        with _APPLY_LOCK:
            row = self.get(proposal_id)
            if row['status'] != 'failed' or any(e['kind'] == 'generation_cancelled' for e in row['events']):
                raise WorkspaceError('Generation is not awaiting a retry decision')
            if not retry:
                with self._db() as db:
                    self._event(db, proposal_id, 'generation_cancelled')
                return self.get(proposal_id)
            project = self.manager.get(row['project_id'])
            baseline = self.baselines / proposal_id
            if project is None or not baseline.is_dir():
                raise WorkspaceError('Original project or proposal baseline unavailable')
            from cmf_dev_studio.projects.intelligence import prepare_context
            paths = row['approved_paths'] if context_paths is None else context_paths
            if len(paths) > 8 or len(set(paths)) != len(paths):
                raise WorkspaceError('Select at most 8 unique reference files')
            context = prepare_context(project.path, paths)
            if context_paths is not None and paths and context_digest != context['digest']:
                raise WorkspaceError('Review and approve repository context before retrying')
            original = {p.relative_to(baseline).as_posix(): p.read_bytes()
                        for p in baseline.rglob('*') if p.is_file() and not p.is_symlink()}
            if any(original.get(f['path']) != f['content'].encode('utf-8') for f in context['files']):
                raise WorkspaceError('Approved context has changed; send a new request to approve it again')
            with self._db() as db:
                db.execute("UPDATE workspace_proposals SET status='queued',error='',agent_stage='',plan='{}' WHERE id=?", (proposal_id,))
                # Preserve the original context for legacy requests before replacing it.
                if not any('context_paths' in e['details'] for e in row['events'] if e['kind'] == 'requested'):
                    db.execute("UPDATE proposal_events SET details=? WHERE proposal_id=? AND kind='requested'", (json.dumps({'context_paths': row['approved_paths']}), proposal_id))
                db.execute('UPDATE workspace_proposals SET approved_paths=? WHERE id=?', (json.dumps(paths), proposal_id))
                self._event(db, proposal_id, 'generation_retry_requested', context_paths=paths, context_changed=context_paths is not None)
            Thread(target=self._generate, args=(proposal_id, row['task'], context, original), daemon=True).start()
            return self.get(proposal_id)

    def _db(self):
        db = sqlite3.connect(self.manager.db_path, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def _get(self, proposal_id: str):
        with self._db() as db:
            row = db.execute('SELECT * FROM workspace_proposals WHERE id=?', (proposal_id,)).fetchone()
        if row is None:
            raise KeyError('Proposal not found')
        return dict(row)

    def preview_file(self, proposal_id: str, path: str) -> dict:
        """Read a proposed file for diff review without modifying the project."""
        proposal = self.get(proposal_id)
        relative = safe_path(path)
        change = next((c for c in proposal['changes'] if c['path'] == path), None)
        if change is None:
            raise WorkspaceError('File is not part of this proposal')
        project = self.manager.get(proposal['project_id'])
        if project is None:
            raise WorkspaceError('Project not found')
        original = project.path / relative
        # No symlinks: neither the project tree nor the isolated proposal tree.
        if original.is_symlink() or any((project.path / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts))):
            raise WorkspaceError('Unsafe original path')
        if change['action'] == 'create':
            before = ''
        else:
            if not original.is_file():
                raise WorkspaceError('Original file no longer exists')
            raw = original.read_bytes()
            if len(raw) > MAX_FILE or digest(raw) != change['before_sha256']:
                raise WorkspaceError('Original file changed since the proposal was created')
            before = raw.decode('utf-8')
        if change['action'] == 'delete':
            after = ''
        else:
            target = self.root / proposal_id / relative
            if target.is_symlink() or not target.is_file() or target.stat().st_size > MAX_FILE:
                raise WorkspaceError('Proposed file unavailable')
            after = target.read_text(encoding='utf-8')
        return {'path': path, 'before': before, 'after': after}

    def get(self, proposal_id: str) -> dict:
        row = self._get(proposal_id)
        row['changes'] = json.loads(row['changes'])
        row['approved_paths'] = json.loads(row['approved_paths'])
        row['plan'] = json.loads(row['plan'])
        with self._db() as db:
            events = db.execute('SELECT sequence,kind,created_at,details FROM proposal_events WHERE proposal_id=? ORDER BY sequence', (proposal_id,)).fetchall()
        row['events'] = [{**dict(event), 'details': json.loads(event['details'])} for event in events]
        return row

    def list(self, project_id: str) -> list[dict]:
        with self._db() as db:
            ids = [r[0] for r in db.execute('SELECT id FROM workspace_proposals WHERE project_id=? ORDER BY created_at DESC', (project_id,))]
        return [self.get(i) for i in ids]

    def submit(self, project_id: str, task: str, selected_paths: list[str], context_digest: str | None = None) -> dict:
        project = self.manager.get(project_id)
        if project is None:
            raise KeyError('Project not found')
        if not task.strip() or len(task) > 4000:
            raise WorkspaceError('Task must be between 1 and 4000 characters')
        if len(selected_paths) > 8 or len(set(selected_paths)) != len(selected_paths):
            raise WorkspaceError('Select at most 8 unique reference files')
        from cmf_dev_studio.projects.intelligence import prepare_context
        context = prepare_context(project.path, selected_paths)
        if selected_paths and context_digest != context['digest']:
            raise WorkspaceError('Review and approve repository context before generating a proposal')
        proposal_id = uuid4().hex
        workspace = self.root / proposal_id
        workspace.mkdir()
        try:
            original = snapshot(project.path, workspace)
        except Exception:
            shutil.rmtree(workspace, ignore_errors=True)
            raise
        for file in context['files']:
            if original.get(file['path']) != file['content'].encode('utf-8'):
                shutil.rmtree(workspace, ignore_errors=True)
                raise WorkspaceError('Approved context changed during snapshot; review again')
        baseline = self.baselines / proposal_id
        baseline.mkdir()
        for name, data in original.items():
            destination = baseline / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        now = datetime.now(timezone.utc).isoformat()
        with self._db() as db:
            db.execute('INSERT INTO workspace_proposals(id,project_id,status,task,created_at,approved_paths) VALUES (?,?,?,?,?,?)', (proposal_id, project_id, 'queued', task, now, json.dumps(selected_paths)))
            self._event(db, proposal_id, 'requested', context_paths=selected_paths)
        Thread(target=self._generate, args=(proposal_id, task, context, original), daemon=True).start()
        return self.get(proposal_id)

    def _update(self, proposal_id: str, status: str, error: str = '', changes: list | None = None):
        with self._db() as db:
            db.execute('UPDATE workspace_proposals SET status=?,error=?,changes=? WHERE id=?', (status, error, json.dumps(changes or []), proposal_id))
            if status == 'ready':
                self._event(db, proposal_id, 'files_generated', count=len(changes or []))
            elif status == 'failed':
                self._event(db, proposal_id, 'generation_failed', error=error)

    def _stage(self, proposal_id: str, stage: str, *, plan: Plan | None = None):
        with self._db() as db:
            if plan is None:
                db.execute('UPDATE workspace_proposals SET agent_stage=? WHERE id=?', (stage, proposal_id))
            else:
                db.execute('UPDATE workspace_proposals SET agent_stage=?,plan=? WHERE id=?',
                           (stage, json.dumps({'requirements': plan.requirements, 'acceptance': plan.acceptance}), proposal_id))
            if stage in ('analyst', 'developer', 'tester', 'developer_repair'):
                self._event(db, proposal_id, 'agent_stage', stage=stage)

    def _write_operations(self, proposal_id: str, operations: list[dict], original: dict[str, bytes]) -> list[dict]:
        workspace = self.root / proposal_id
        # Clear previous generated files, never the baseline or the real project.
        for stale in sorted(workspace.rglob('*'), reverse=True):
            if stale.is_symlink():
                stale.unlink()
            elif stale.is_file():
                stale.unlink()
            elif stale.is_dir():
                try:
                    stale.rmdir()
                except OSError:
                    pass
        for relative, previous in original.items():
            dest = workspace / safe_path(relative)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(previous)
        changes = []
        for operation in operations:
            action, path = operation['action'], operation['path']
            relative = safe_path(path)
            previous = original.get(path)
            content = '' if action == 'delete' else operation['content']
            dest = workspace / relative
            if action == 'delete':
                dest.unlink(missing_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding='utf-8')
            before = previous.decode('utf-8') if previous is not None else ''
            diff = ''.join(difflib.unified_diff(before.splitlines(keepends=True), content.splitlines(keepends=True),
                fromfile=f'a/{path}' if previous is not None else '/dev/null',
                tofile=f'b/{path}' if action != 'delete' else '/dev/null'))
            changes.append({'action': action, 'path': path, 'diff': diff,
                            'before_sha256': digest(previous), 'size': len(content.encode('utf-8'))})
        return changes

    def repair(self, proposal_id: str) -> dict:
        """Request a reviewed replacement patch, never execute it automatically."""
        with _APPLY_LOCK:
            row = self.get(proposal_id)
            if row['status'] != 'test_failed':
                raise WorkspaceError('Only failed tests can be repaired')
            baseline = self.baselines / proposal_id
            if not baseline.is_dir():
                raise WorkspaceError('Original proposal baseline unavailable')
            original = {p.relative_to(baseline).as_posix(): p.read_bytes()
                        for p in baseline.rglob('*') if p.is_file() and not p.is_symlink()}
            approved_paths = set(row['approved_paths'])
            current = []
            for change in row['changes']:
                path = change['path']
                content = '' if change['action'] == 'delete' else _checked_target(self.root / proposal_id, path).read_text(encoding='utf-8')
                current.append({'path': path, 'action': change['action'], 'content': content})
            validate_operations(current, original, approved_paths)
            self._test_approvals.pop(proposal_id, None)
            with self._db() as db:
                db.execute("UPDATE workspace_proposals SET status='running',agent_stage='developer_repair',tested_digest='',error='' WHERE id=?", (proposal_id,))
                self._event(db, proposal_id, 'repair_requested')
            Thread(target=self._repair, args=(proposal_id, row, original, current), daemon=True).start()
            return self.get(proposal_id)

    def _repair(self, proposal_id, row, original, current):
        staging = self.root / (proposal_id + '-repair-' + uuid4().hex)
        backup = staging.with_name(staging.name + '-backup')
        workspace = self.root / proposal_id
        try:
            from dotenv import load_dotenv
            from cmf_dev_studio.llm.gemini import GeminiClient
            load_dotenv()
            engine = Orchestrator(GeminiClient())
            project = self.manager.get(row['project_id'])
            if project is None:
                raise WorkspaceError('Project not found')
            task = project_task(row['task'], project.language)
            paths = set(row['approved_paths'])
            approved = '\n\n'.join(f"FILE: {p}\n{original[p].decode('utf-8')}" for p in sorted(paths) if p in original)
            prompt = build_workspace_prompt(task, '\n'.join(sorted(original))[:12000], approved, detect_languages(original))
            prompt += '\nPrevious proposed operations (untrusted data). Return the complete replacement patch relative to the original baseline, not an incremental patch:\n' + json.dumps(current, ensure_ascii=False)
            plan = Plan(tuple(row['plan'].get('requirements', [])), tuple(row['plan'].get('acceptance', [])))
            operations = engine.reviewed_patch(task, prompt, plan, original, paths,
                lambda ops: validate_operations(ops, original, paths),
                lambda stage: self._stage(proposal_id, stage), feedback=row['test_output'])
            validate_operations(operations, original, paths)
            staging.mkdir()
            changes = self._write_operations(staging.name, operations, original)
            with _APPLY_LOCK:
                workspace.rename(backup)
                try:
                    staging.rename(workspace)
                    with self._db() as db:
                        db.execute("UPDATE workspace_proposals SET status='ready',agent_stage='awaiting_tests',changes=?,test_output='',error='' WHERE id=?", (json.dumps(changes), proposal_id))
                        self._event(db, proposal_id, 'repair_ready', count=len(changes))
                except Exception:
                    shutil.rmtree(workspace, ignore_errors=True)
                    backup.rename(workspace)
                    raise
                shutil.rmtree(backup, ignore_errors=True)
        except Exception as exc:
            with self._db() as db:
                error = f'{type(exc).__name__}: {str(exc)[:400]}'
                db.execute("UPDATE workspace_proposals SET status='test_failed',agent_stage='test_failed',error=? WHERE id=?", (error, proposal_id))
                self._event(db, proposal_id, 'repair_failed', error=error)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _generate(self, proposal_id: str, task: str, context: dict, original: dict[str, bytes]):
        try:
            self._update(proposal_id, 'running')
            from dotenv import load_dotenv
            from cmf_dev_studio.llm.gemini import GeminiClient
            load_dotenv()
            client = GeminiClient()
            engine = Orchestrator(client)
            inventory = '\n'.join(sorted(original))[:12000]
            approved = '\n\n'.join(f"FILE: {f['path']}\n{f['content']}" for f in context['files'])
            approved_paths = {f['path'] for f in context['files']}
            project = self.manager.get(self.get(proposal_id)['project_id'])
            if project is None:
                raise WorkspaceError('Project not found')
            task = project_task(task, project.language)
            languages = detect_languages(original)
            operations = engine.prepare(task, inventory, approved, languages, original, approved_paths,
                lambda ops: validate_operations(ops, original, approved_paths),
                lambda stage: self._stage(proposal_id, stage),
                lambda plan: self._stage(proposal_id, 'developer', plan=plan))
            changes = self._write_operations(proposal_id, operations, original)
            self._update(proposal_id, 'ready', changes=changes)
            self._stage(proposal_id, 'awaiting_tests')
        except Exception as exc:
            self._stage(proposal_id, 'failed')
            self._update(proposal_id, 'failed', error=f'{type(exc).__name__}: {str(exc)[:400]}')

# v2.2: verified application and isolated project-level test execution.
import threading

_APPLY_LOCK = threading.RLock()


def _checked_target(root: Path, path: str) -> Path:
    relative = safe_path(path)
    target = root / relative
    if root.is_symlink() or not root.is_dir():
        raise WorkspaceError('Project directory is no longer safe')
    for parent in [root, *(root / Path(*relative.parts[:i]) for i in range(1, len(relative.parts)))]:
        if parent.is_symlink():
            raise WorkspaceError(f'Symlink in destination path: {path}')
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise WorkspaceError(f'Unsafe destination: {path}')
    return target


def _test_details(self: WorkspaceService, proposal_id: str) -> dict:
    row = self.get(proposal_id)
    if self.manager.get(row['project_id']) is None:
        raise WorkspaceError('Project no longer exists')
    if row['status'] not in ('ready', 'tested', 'test_failed'):
        raise WorkspaceError('Proposal must be ready before testing')
    workspace = self.root / proposal_id
    if not workspace.is_dir():
        raise WorkspaceError('Proposal workspace missing')
    try:
        spec = select_runner(workspace)
    except UnsupportedRunner as exc:
        raise WorkspaceError(str(exc)) from exc
    command = list(spec.command)
    approval = hashlib.sha256(json.dumps([proposal_id, tree_digest(workspace), command]).encode()).hexdigest()
    return {'command': command, 'approval': approval, 'working_directory': 'Temporary copy of proposal', 'timeout': spec.timeout}


def _test_preview(self: WorkspaceService, proposal_id: str) -> dict:
    with _APPLY_LOCK:
        details = _test_details(self, proposal_id)
        token = uuid4().hex
        self._test_approvals[proposal_id] = (token, details['approval'])
        return {**details, 'approval': token}


def _test_proposal(self: WorkspaceService, proposal_id: str, approval: str = '') -> dict:
    with _APPLY_LOCK:
        preview = _test_details(self, proposal_id)
        expected = self._test_approvals.get(proposal_id)
        if not approval or expected != (approval, preview['approval']):
            raise WorkspaceError('Explicit approval of the current command and proposal is required')
        self._test_approvals.pop(proposal_id, None)
        workspace = self.root / proposal_id
        spec = select_runner(workspace)
        before = tree_digest(workspace)
        with self._db() as db:
            db.execute("UPDATE workspace_proposals SET status='running',tested_digest='',agent_stage='testing' WHERE id=?", (proposal_id,))
            self._event(db, proposal_id, 'command_approved', command=preview['command'])
        try:
            passed, output = execute_runner(workspace, spec)
            if tree_digest(workspace) != before:
                passed, output = False, 'Workspace changed during testing; verification invalidated'
        except Exception as exc:
            passed, output = False, f'Runner infrastructure error: {exc}'
        with self._db() as db:
            db.execute('UPDATE workspace_proposals SET status=?,tested_digest=?,agent_stage=?,attempts=attempts+1,test_output=? WHERE id=?',
                       ('tested' if passed else 'test_failed', before if passed else '', 'verified' if passed else 'test_failed', output, proposal_id))
            self._event(db, proposal_id, 'tests_passed' if passed else 'tests_failed', output=output)
        return self.get(proposal_id)

def _apply_proposal(self: WorkspaceService, proposal_id: str, approved: bool, allow_existing: bool = False) -> dict:
    with _APPLY_LOCK:
        row = self.get(proposal_id)
        if row['status'] != 'tested':
            raise WorkspaceError('Only proposals with passing project tests may be applied')
        project = self.manager.get(row['project_id'])
        if project is None:
            raise WorkspaceError('Project no longer exists')
        if approved is not True:
            raise WorkspaceError('Explicit approval is required to apply changes')
        if project.kind.value == 'existing' and not allow_existing:
            raise WorkspaceError('Existing projects require explicit write authorization')
        root = project.path
        workspace = self.root / proposal_id
        changes = row['changes']
        if not row['tested_digest'] or tree_digest(workspace) != row['tested_digest']:
            raise WorkspaceError('Isolated workspace changed after testing; retest before applying')
        if not changes:
            raise WorkspaceError('No changes to apply')
        prepared = []
        # Validate the complete transaction before touching any project file.
        for change in changes:
            path = change['path']
            target = _checked_target(root, path)
            old = target.read_bytes() if target.exists() else None
            if digest(old) != change['before_sha256']:
                raise WorkspaceError(f'Conflict: {path} changed since the proposal was generated')
            new = None if change['action'] == 'delete' else (workspace / safe_path(path)).read_bytes()
            if new is not None and (len(new) > MAX_FILE or b'\x00' in new):
                raise WorkspaceError(f'Unsafe proposed content: {path}')
            prepared.append((target, old, new))
        backup = self.root / (proposal_id + '-backup')
        backup.mkdir(exist_ok=False)
        touched = []
        try:
            for index, (target, old, new) in enumerate(prepared):
                # Recheck immediately before writing; other writers should not edit during apply.
                if digest(target.read_bytes() if target.exists() else None) != digest(old):
                    raise WorkspaceError(f'Conflict during apply: {target.name}')
                _checked_target(root, str(target.relative_to(root).as_posix()))
                if old is not None:
                    (backup / str(index)).write_bytes(old)
                target.parent.mkdir(parents=True, exist_ok=True)
                touched.append((target, old))
                if new is None:
                    target.unlink()
                else:
                    temporary = target.with_name(target.name + '.studio-tmp-' + proposal_id)
                    try:
                        temporary.write_bytes(new)
                        os.replace(temporary, target)
                    finally:
                        temporary.unlink(missing_ok=True)
            with self._db() as db:
                db.execute("UPDATE workspace_proposals SET status='applied' WHERE id=? AND status='tested'", (proposal_id,))
                self._event(db, proposal_id, 'changes_applied', count=len(changes))
        except Exception:
            for target, old in reversed(touched):
                if old is None:
                    target.unlink(missing_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(old)
            raise
        finally:
            shutil.rmtree(backup, ignore_errors=True)
        return self.get(proposal_id)


WorkspaceService.test_preview = _test_preview
WorkspaceService.test = _test_proposal
WorkspaceService.apply = _apply_proposal
