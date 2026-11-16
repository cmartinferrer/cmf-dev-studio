"""Generation retry decisions persist and preserve the approved context."""
import pytest
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.projects.intelligence import prepare_context
from cmf_dev_studio.workspaces import WorkspaceService, WorkspaceError
import cmf_dev_studio.workspaces as workspaces


@pytest.fixture
def failed(tmp_path, monkeypatch):
    manager = ProjectManager(tmp_path / 'data')
    project = manager.create('sample')
    (project.path / 'main.py').write_text('x = 1\n')
    service = WorkspaceService(manager)
    calls = []
    class FakeThread:
        def __init__(self, target, args, daemon):
            calls.append(args)
        def start(self):
            pass
    monkeypatch.setattr(workspaces, 'Thread', FakeThread)
    context = prepare_context(project.path, ['main.py'])
    row = service.submit(project.id, 'change x', ['main.py'], context['digest'])
    service._update(row['id'], 'failed', error='503 UNAVAILABLE')
    return service, project, row['id'], calls


def test_retry_keeps_request_and_history(failed):
    """Reuse the approved task and files; keep each failure and retry decision."""
    service, project, pid, calls = failed
    assert service.retry_generation(pid)['status'] == 'queued'
    assert calls[0] == calls[1]
    with pytest.raises(WorkspaceError):
        service.retry_generation(pid)
    service._update(pid, 'failed', error='503 again')
    service.retry_generation(pid)
    row = WorkspaceService(service.manager).get(pid)
    assert [e['kind'] for e in row['events']] == ['requested','generation_failed','generation_retry_requested','generation_failed','generation_retry_requested']
    assert row['task'] == 'change x'
    assert row['approved_paths'] == ['main.py']


def test_cancel_persists(failed):
    """Cancellation is recorded and never starts a new model call."""
    service, _, pid, calls = failed
    service.retry_generation(pid, False)
    reopened = WorkspaceService(service.manager)
    assert reopened.get(pid)['events'][-1]['kind'] == 'generation_cancelled'
    with pytest.raises(WorkspaceError):
        reopened.retry_generation(pid)
    assert len(calls) == 1


def test_changed_context_requires_new_request(failed):
    """Do not send changed file contents under the original approval."""
    service, project, pid, calls = failed
    (project.path / 'main.py').write_text('x = 2\n')
    with pytest.raises(WorkspaceError, match='context has changed'):
        service.retry_generation(pid)
    assert len(calls) == 1


def test_retry_with_explicit_replacement_context(failed):
    """Record the original and replacement contexts separately."""
    service, project, pid, calls = failed
    row = service.retry_generation(pid, True, [], None)
    assert row['approved_paths'] == []
    assert row['events'][0]['details']['context_paths'] == ['main.py']
    assert row['events'][-1]['details']['context_paths'] == []
    assert calls[-1][2]['files'] == []


def test_retry_replacement_requires_digest(failed):
    """Do not accept replacement files without explicit content approval."""
    service, project, pid, calls = failed
    with pytest.raises(WorkspaceError, match='Review and approve'):
        service.retry_generation(pid, True, ['main.py'], 'wrong')
    assert len(calls) == 1
