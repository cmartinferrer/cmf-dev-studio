"""Conversation persistence, migration and isolation regression tests."""

import pytest

from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService


def test_conversations(tmp_path, monkeypatch):
    """Keep separate histories and discard only conversation data."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample")
    other = manager.create("other")
    service = WorkspaceService(manager)
    monkeypatch.setattr(service, "_generate", lambda *args: None)
    first = service.create_conversation(project.id)
    second = service.create_conversation(project.id)
    a = service.submit(project.id, "First request", [], conversation_id=first["id"])
    b = service.submit(project.id, "Second request", [], conversation_id=second["id"])
    assert [p["id"] for p in service.list(project.id, first["id"])] == [a["id"]]
    assert service._investigation_history(b["id"], b) == []
    with pytest.raises(KeyError):
        service.submit(other.id, "Invalid", [], conversation_id=first["id"])
    with pytest.raises(WorkspaceError):
        service.remove_conversation(project.id, first["id"])
    service._update(a["id"], "answered")
    (project.path / "keep.txt").write_text("keep")
    service.rename_conversation(project.id, first["id"], "Renamed")
    service.remove_conversation(project.id, first["id"], clear=True)
    assert service.list(project.id, first["id"]) == []
    assert (project.path / "keep.txt").read_text() == "keep"
    assert service.get(b["id"])["task"] == "Second request"
    assert any(
        c["title"] == "Renamed"
        for c in WorkspaceService(manager).conversations(project.id)
    )


def test_legacy_migration(tmp_path):
    """Existing proposals retain their IDs and events after migration."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample")
    service = WorkspaceService(manager)
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (
                "legacy",
                project.id,
                "answered",
                "Old request",
                "2026-01-01T00:00:00+00:00",
            ),
        )
        service._event(db, "legacy", "assistant_response", message="Old answer")
    migrated = WorkspaceService(manager)
    conversations = migrated.conversations(project.id)
    assert len(conversations) == 1
    assert (
        migrated.list(project.id, conversations[0]["id"])[0]["events"][0]["details"][
            "message"
        ]
        == "Old answer"
    )
    assert len(WorkspaceService(manager).conversations(project.id)) == 1
