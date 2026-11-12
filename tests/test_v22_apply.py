from pathlib import Path
import json
import pytest
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceService, WorkspaceError, digest, tree_digest


def proposal(tmp_path, existing=False):
    manager = ProjectManager(tmp_path / 'data')
    if existing:
        source = tmp_path / 'source'
        source.mkdir()
        project = manager.register_existing(source, 'sample')
    else:
        project = manager.create('sample')
    service = WorkspaceService(manager)
    proposal_id = 'a' * 32
    workspace = service.root / proposal_id
    workspace.mkdir()
    (workspace / 'main.py').write_text('print(2)\n')
    with service._db() as db:
        db.execute("INSERT INTO workspace_proposals(id,project_id,status,task,created_at,changes,tested_digest) VALUES (?,?,?,?,?,?,?)", (proposal_id,project.id,'tested','task','now',json.dumps([{'action':'create','path':'main.py','before_sha256':None,'size':9,'diff':''}]),tree_digest(workspace)))
    return service, project, proposal_id


def test_apply_managed(tmp_path):
    service, project, pid = proposal(tmp_path)
    with pytest.raises(WorkspaceError, match='exact project name'):
        service.apply(pid, 'wrong')
    assert service.apply(pid, 'sample')['status'] == 'applied'
    assert (project.path / 'main.py').read_text() == 'print(2)\n'


def test_apply_existing_requires_authorization(tmp_path):
    service, project, pid = proposal(tmp_path, True)
    with pytest.raises(WorkspaceError, match='explicit write authorization'):
        service.apply(pid, 'sample')
    assert not (project.path / 'main.py').exists()
    assert service.apply(pid, 'sample', True)['status'] == 'applied'


def test_apply_conflict(tmp_path):
    service, project, pid = proposal(tmp_path)
    (project.path / 'main.py').write_text('changed')
    with pytest.raises(WorkspaceError, match='Conflict'):
        service.apply(pid, 'sample')
    assert (project.path / 'main.py').read_text() == 'changed'


def test_symlink_rejected(tmp_path):
    service, project, pid = proposal(tmp_path)
    outside = tmp_path / 'outside'
    outside.write_text('safe')
    (project.path / 'main.py').symlink_to(outside)
    with pytest.raises(WorkspaceError, match='Unsafe destination'):
        service.apply(pid, 'sample')
    assert outside.read_text() == 'safe'
