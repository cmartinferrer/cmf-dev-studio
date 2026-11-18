"""Keep historical reviews while releasing completed proposal snapshots."""

from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceService, tree_digest


def seed(service, project, pid, status):
    """Create a persisted proposal with unrelated snapshot files."""
    for root in (service.root, service.baselines):
        folder = root / pid
        folder.mkdir()
        (folder / "unrelated.py").write_text("value = 1\n")
        (folder / "changed.py").write_text("value = 2\n")
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) "
            "VALUES (?,?,?,?,?)",
            (pid, project.id, status, "task", "now"),
        )


def test_answer_releases_snapshots_and_keeps_digest(tmp_path):
    """An answer needs no file copies but retains its snapshot identity."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)
    pid = "a" * 32
    seed(service, project, pid, "running")
    expected = tree_digest(service.baselines / pid)
    service._update(pid, "answered")
    assert not (service.root / pid).exists()
    assert not (service.baselines / pid).exists()
    assert service.get(pid)["snapshot_digest"] == expected


def test_startup_compacts_applied_and_preserves_pending(tmp_path):
    """Historical diffs survive repeated cleanup and pending work is untouched."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)
    pid, pending = "b" * 32, "c" * 32
    seed(service, project, pid, "running")
    seed(service, project, pending, "ready")
    original = {"changed.py": b"value = 2\n", "unrelated.py": b"value = 1\n"}
    changes = service._write_operations(
        pid,
        [{"action": "modify", "path": "changed.py", "content": "value = 3\n"}],
        original,
    )
    service._update(pid, "applied", changes=changes)
    expected = tree_digest(service.baselines / pid)
    for _ in range(2):
        service = WorkspaceService(manager)
        assert service.get(pid)["snapshot_digest"] == expected
        assert service.preview_file(pid, "changed.py") == {
            "path": "changed.py",
            "before": "value = 2\n",
            "after": "value = 3\n",
        }
        for root in (service.root, service.baselines):
            assert not (root / pid / "unrelated.py").exists()
            assert (root / pending / "unrelated.py").exists()


def test_cancelled_generation_releases_snapshots(tmp_path):
    """Cancelling a retry releases copies but preserves the conversation event."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)
    pid = "d" * 32
    seed(service, project, pid, "failed")
    service.retry_generation(pid, retry=False)
    assert service.get(pid)["events"][-1]["kind"] == "generation_cancelled"
    assert not (service.root / pid).exists()
    assert not (service.baselines / pid).exists()


def test_startup_removes_only_unregistered_snapshot_directories(tmp_path):
    """Unknown files, recovery backups and registered snapshots are retained."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)
    pending = "e" * 32
    orphan = "f" * 32
    seed(service, project, pending, "ready")
    for root in (service.root, service.baselines):
        for name in (orphan, orphan + "-backup", "unknown"):
            (root / name).mkdir()
    service = WorkspaceService(manager)
    for root in (service.root, service.baselines):
        assert not (root / orphan).exists()
        assert (root / pending).exists()
        assert (root / (orphan + "-backup")).exists()
        assert (root / "unknown").exists()


def test_remove_project_releases_history_and_snapshots(tmp_path):
    """Unregistering a project preserves source files but releases internal data."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    (project.path / "main.py").write_text("keep")
    service = WorkspaceService(manager)
    conversation = service.create_conversation(project.id)
    pid = "a" * 32
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at,conversation_id) VALUES (?,?,?,?,?,?)",
            (pid, project.id, "ready", "task", "now", conversation["id"]),
        )
        service._event(db, pid, "files_generated")
    for root in (service.root, service.baselines):
        (root / pid).mkdir()
    assert service.remove_project(project.id)
    assert (project.path / "main.py").read_text() == "keep"
    assert manager.get(project.id) is None
    with service._db() as db:
        for table in ("workspace_proposals", "proposal_events", "conversations"):
            assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert not (service.root / pid).exists()
    assert not (service.baselines / pid).exists()


def test_submit_defers_workspace_until_patch(tmp_path, monkeypatch):
    """Questions and pending exploration only need an immutable baseline."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    (project.path / "main.py").write_text("value = 1\n")
    service = WorkspaceService(manager)
    monkeypatch.setattr("cmf_dev_studio.workspaces.Thread.start", lambda self: None)
    proposal = service.submit(project.id, "Explain this project", [])
    pid = proposal["id"]
    assert (service.baselines / pid / "main.py").read_text() == "value = 1\n"
    assert not (service.root / pid).exists()
    changes = service._write_operations(
        pid,
        [{"action": "modify", "path": "main.py", "content": "value = 2\n"}],
        {"main.py": b"value = 1\n"},
    )
    assert len(changes) == 1
    assert (service.root / pid / "main.py").read_text() == "value = 2\n"
    assert (service.baselines / pid / "main.py").read_text() == "value = 1\n"
    assert (project.path / "main.py").read_text() == "value = 1\n"
