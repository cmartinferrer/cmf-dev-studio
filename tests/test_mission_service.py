import time
from threading import Event

import pytest
from fastapi.testclient import TestClient

from multi_agent_software_team.api.app import create_app
from multi_agent_software_team.events import EventType, ExecutionEvent
from multi_agent_software_team.missions import MissionService
from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.projects import ProjectManager


def wait_for(service, run_id):
    for _ in range(200):
        value = service.get(run_id)
        if value['status'] in ('completed', 'failed'):
            return value
        time.sleep(.01)
    pytest.fail('Mission did not complete')


def test_mission_persists_result_and_events(tmp_path):
    manager = ProjectManager(tmp_path)
    project = manager.create('Test')

    def execute(mission, emit):
        emit(ExecutionEvent(type=EventType.MISSION_STARTED))
        mission.code = 'print(1)'
        mission.status = MissionStatus.COMPLETED
        return mission

    service = MissionService(manager, execute=execute)
    run = service.submit(project.id, 'Make a program')
    completed = wait_for(service, run['id'])
    assert completed['result']['code'] == 'print(1)'
    assert service.events(run['id'])[0]['type'] == 'mission_started'
    assert MissionService(ProjectManager(tmp_path)).get(run['id'])['status'] == 'completed'
    assert service.list_for_project(project.id)[0]['id'] == run['id']


def test_one_active_mission_per_project(tmp_path):
    manager = ProjectManager(tmp_path)
    project = manager.create('Test')
    gate = Event()

    def execute(mission, emit):
        gate.wait(timeout=3)
        mission.status = MissionStatus.COMPLETED
        return mission

    service = MissionService(manager, execute=execute)
    first = service.submit(project.id, 'First')
    with pytest.raises(ValueError, match='already active'):
        service.submit(project.id, 'Second')
    gate.set()
    assert wait_for(service, first['id'])['status'] == 'completed'


def test_error_is_persisted(tmp_path):
    manager = ProjectManager(tmp_path)
    project = manager.create('Test')

    def execute(mission, emit):
        raise RuntimeError('LLM unavailable')

    service = MissionService(manager, execute=execute)
    run = service.submit(project.id, 'Task')
    assert 'LLM unavailable' in wait_for(service, run['id'])['error']


def test_unknown_project_and_invalid_description(tmp_path):
    manager = ProjectManager(tmp_path)
    service = MissionService(manager)
    with pytest.raises(KeyError):
        service.submit('missing', 'Task')
    project = manager.create('Test')
    with pytest.raises(ValueError):
        service.submit(project.id, '   ')


def test_mission_api_endpoints(tmp_path):
    client = TestClient(create_app(tmp_path))
    project = client.post('/api/projects', json={'name': 'Demo'}).json()
    assert client.get(f"/api/projects/{project['id']}/missions").json() == []
    assert client.get('/api/missions/missing').status_code == 404
    assert client.get('/api/missions/missing/events').status_code == 404
    assert client.post('/api/projects/missing/missions', json={'description': 'Task'}).status_code == 404


def test_recover_interrupted_missions_releases_project(tmp_path):
    manager = ProjectManager(tmp_path)
    project = manager.create('Restarted')
    other = manager.create('Other')
    service = MissionService(manager)
    from uuid import uuid4
    from multi_agent_software_team.missions import _now
    with service._db() as db:
        for state in ('running', 'queued'):
            db.execute('INSERT INTO mission_runs (id,project_id,description,status,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                       (str(uuid4()), project.id if state == 'running' else other.id, 'Task', state, _now(), _now()))
    assert service.recover_interrupted() == 2
    assert service.recover_interrupted() == 0
    runs = service.list_for_project(project.id)
    assert runs[0]['status'] == 'failed'
    assert 'interrupted' in runs[0]['error']
    assert service.events(runs[0]['id']) == []


def test_api_initialization_recovers_stale_runs(tmp_path):
    manager = ProjectManager(tmp_path)
    project = manager.create('Demo')
    service = MissionService(manager)
    from multi_agent_software_team.missions import _now
    with service._db() as db:
        db.execute('INSERT INTO mission_runs (id,project_id,description,status,created_at,updated_at) VALUES (?,?,?,?,?,?)',
                   ('old-run', project.id, 'Task', 'running', _now(), _now()))
    client = TestClient(create_app(tmp_path))
    response = client.get('/api/missions/old-run')
    assert response.status_code == 200
    assert response.json()['status'] == 'failed'
    assert 'restart' in response.json()['error']
