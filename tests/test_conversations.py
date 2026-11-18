"""Conversation persistence and isolation regression tests."""

import pytest

from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService


def test_conversations(tmp_path, monkeypatch):
    """Keep separate histories and discard only conversation data."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    other = manager.create("other", location=tmp_path)
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
