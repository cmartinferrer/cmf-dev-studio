"""Regression coverage for exploration decisions and historical reviews."""

import pytest

from cmf_dev_studio.contracts import Plan
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService


@pytest.fixture
def proposal(tmp_path):
    """Create a proposal with a real project and immutable baseline."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)
    pid = "sample"
    (service.root / pid).mkdir()
    (service.baselines / pid).mkdir()
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at,assistant_language) VALUES (?,?,?,?,?,?)",
            (pid, project.id, "awaiting_exploration", "task", "now", "Spanish"),
        )
    return service, project, pid


def test_denial_records_response_without_investigation(proposal, monkeypatch):
    """Declining exploration ends the request without invoking the model."""
    service, _, pid = proposal

    def forbidden(*args, **kwargs):
        pytest.fail("Exploration must not run after denial")

    monkeypatch.setattr(service, "_generate", forbidden)
    result = service.exploration_decision(pid, False)
    assert result["status"] == "answered"
    assert [e["kind"] for e in result["events"]] == [
        "exploration_denied",
        "assistant_response",
    ]
    assert "No exploraré" in result["events"][-1]["details"]["message"]
    assert result["approved_paths"] == []


def test_applied_review_uses_baseline_but_pending_review_detects_conflict(proposal):
    """Historical diffs remain readable without weakening pending conflict checks."""
    service, project, pid = proposal
    path = "sample.py"
    original = b"value = 1\n"
    (project.path / path).write_bytes(original)
    (service.baselines / pid / path).write_bytes(original)
    operations = [{"action": "modify", "path": path, "content": "value = 2\n"}]
    service._update(
        pid,
        "ready",
        changes=service._write_operations(pid, operations, {path: original}),
    )
    (project.path / path).write_text("value = 2\n")
    with pytest.raises(WorkspaceError, match="Original file changed"):
        service.preview_file(pid, path)
    with service._db() as db:
        db.execute("UPDATE workspace_proposals SET status='applied' WHERE id=?", (pid,))
    (project.path / path).write_text("value = 3\n")
    assert service.preview_file(pid, path) == {
        "path": path,
        "before": "value = 1\n",
        "after": "value = 2\n",
    }


def test_saving_plan_does_not_duplicate_developer_activity(proposal):
    """Record actual stage starts, not the plan persistence callback."""
    service, _, pid = proposal
    service._stage(pid, "developer", plan=Plan(("task",), ("result",)))
    service._stage(pid, "developer")
    result = service.get(pid)
    assert result["plan"]["requirements"] == ["task"]
    assert [e["details"]["stage"] for e in result["events"]] == ["developer"]


def test_investigation_history_invalidates_changed_snapshot(proposal):
    """Keep intent, not obsolete answers, after a dependency changes."""
    service, project, pid = proposal
    old = service.baselines / pid
    (old / "MessageService.java").write_text("return null;")
    with service._db() as db:
        service._event(db, pid, "assistant_response", message="Returns null")
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            ("next", project.id, "queued", "current behavior", "zzz"),
        )
    current = service.baselines / "next"
    current.mkdir()
    dependency = current / "MessageService.java"
    dependency.write_text("return null;")
    row = service.get("next")
    history = service._investigation_history("next", row)
    assert history == [
        {"task": "task", "response": "Returns null", "snapshot_unchanged": True}
    ]
    dependency.write_text('return "CMF Dev Studio";')
    history = service._investigation_history("next", row)
    assert history == [{"task": "task", "response": "", "snapshot_unchanged": False}]
    assert service.get(pid)["events"][-1]["details"]["message"] == "Returns null"
    dependency.unlink()
    assert not service._investigation_history("next", row)[0]["snapshot_unchanged"]
