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


def test_recommendation_survives_applied_changes_and_restart(tmp_path, monkeypatch):
    """Resolve advice from the same chat without trusting stale source answers."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)
    monkeypatch.setattr(service, "_generate", lambda *args: None)
    chat = service.create_conversation(project.id)["id"]
    other = service.create_conversation(project.id)["id"]
    source = project.path / "calculator.py"
    source.write_text("def add(a, b): return a + b\n")
    first = service.submit(project.id, "Add maximum", [], conversation_id=chat)
    advice = "Refactor calculator.py CLI using a dispatcher dictionary."
    service._record_recommendation(first["id"], advice)
    with service._db() as db:
        service._event(
            db, first["id"], "assistant_response", message="Old source claim"
        )
    service._update(first["id"], "applied")
    source.write_text("def maximum(a, b): return max(a, b)\n")
    service = WorkspaceService(manager)
    monkeypatch.setattr(service, "_generate", lambda *args: None)
    followup = service.submit(project.id, "Apply your advice", [], conversation_id=chat)
    history = service._investigation_history(followup["id"], followup)
    assert history == [
        {
            "task": "Add maximum",
            "response": "",
            "snapshot_unchanged": False,
            "recommendation": advice,
            "outcome": "applied",
        }
    ]
    task = service._with_conversation_context(
        "Apply your advice", followup["id"], followup
    )
    assert advice in task
    assert "Old source claim" not in task
    isolated = service.submit(project.id, "Apply advice", [], conversation_id=other)
    assert service._investigation_history(isolated["id"], isolated) == []
