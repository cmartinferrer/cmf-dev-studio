"""Persistent activity history for approved local execution."""
import json
import pytest
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceService, WorkspaceError
import cmf_dev_studio.workspaces as workspaces


def test_history_survives_restart_and_multiple_attempts(tmp_path, monkeypatch):
    """Keep decisions and each test output after applying and reopening."""
    manager = ProjectManager(tmp_path / 'data')
    project = manager.create('sample')
    service = WorkspaceService(manager)
    pid = 'b' * 32
    workspace = service.root / pid
    workspace.mkdir()
    (workspace / 'test_sample.py').write_text('def test_sample(): pass\n')
    with service._db() as db:
        db.execute('INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)', (pid, project.id, 'queued', 'task', 'now'))
    service._update(pid, 'ready', changes=[{'action':'create','path':'test_sample.py','before_sha256':None}])
    preview = service.test_preview(pid)
    service.defer(pid, 'tests')
    with pytest.raises(WorkspaceError, match='Explicit approval'):
        service.test(pid, preview['approval'])
    results = iter([(False, 'first failure'), (True, 'second success')])
    monkeypatch.setattr(workspaces, 'execute_runner', lambda *_: next(results))
    for _ in range(2):
        service.test(pid, service.test_preview(pid)['approval'])
    service.defer(pid, 'apply')
    service.apply(pid, True)
    events = WorkspaceService(manager).list(project.id)[0]['events']
    assert [e['kind'] for e in events] == ['files_generated','tests_skipped','command_approved','tests_failed','command_approved','tests_passed','apply_deferred','changes_applied']
    assert [e['details']['output'] for e in events if 'output' in e['details']] == ['first failure','second success']
    assert events[2]['details']['command']
    assert 'approval' not in events[2]['details']
    with pytest.raises(WorkspaceError):
        service.defer(pid, 'tests')


def test_legacy_proposal_has_empty_history(tmp_path):
    """Do not invent historical actions for existing proposals."""
    manager = ProjectManager(tmp_path / 'data')
    service = WorkspaceService(manager)
    with service._db() as db:
        db.execute('INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)', ('old','project','applied','task','now'))
    assert service.get('old')['events'] == []
