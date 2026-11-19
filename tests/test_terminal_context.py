"""Terminal snapshots remain bounded, untrusted and independent of file approvals."""

import pytest

from cmf_dev_studio import workspaces
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.terminal_context import (
    normalize_terminal_context,
    with_terminal_context,
)
from cmf_dev_studio.workspaces import WorkspaceService


def test_snapshot_validation():
    """Mask credentials and reject oversized or duplicate snapshots."""
    item = {"id": 1, "name": "Run", "output": "password=example\nERROR"}
    result = normalize_terminal_context([item])
    assert result[0]["output"] == "password=[REDACTED]\nERROR"
    with pytest.raises(ValueError):
        normalize_terminal_context([item, item])
    with pytest.raises(ValueError):
        normalize_terminal_context([{**item, "output": "x" * 12001}])
    assert "untrusted data" in with_terminal_context("", result)
    assert with_terminal_context("files", []) == "files"


def test_snapshot_persists_on_retry(tmp_path, monkeypatch):
    """Keep the original snapshot without implicitly approving any files."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)

    class FakeThread:
        def __init__(self, target, args, daemon):
            pass

        def start(self):
            pass

    monkeypatch.setattr(workspaces, "Thread", FakeThread)
    item = {"id": 1, "name": "Run", "output": "ERROR main.py"}
    row = service.submit(project.id, "Fix error", [], terminal_context=[item])
    assert row["approved_paths"] == []
    assert row["terminal_context"] == [item]
    service._update(row["id"], "failed", error="503")
    reopened = WorkspaceService(manager)
    assert reopened.retry_generation(row["id"])["terminal_context"] == [item]


def test_api_passes_terminal_evidence_to_agents(tmp_path, monkeypatch):
    """Send bounded evidence to the existing orchestrator without file approval."""
    import sys
    import types

    from fastapi.testclient import TestClient

    from cmf_dev_studio.api.app import create_app

    prompts = []

    class FakeEngine:
        def __init__(
            self,
            client,
            *,
            on_recommendation=None,
            independent_recommendations=False,
            skills=None,
            on_critical_recommendation=None,
        ):
            assert independent_recommendations is True

        def prepare(
            self,
            task,
            inventory,
            approved,
            languages,
            original,
            approved_paths,
            validate,
            stage,
            save_plan,
        ):
            prompts.append((task, approved, approved_paths))
            return [{"action": "create", "path": "fix.py", "content": "x = 1\n"}]

    class InlineThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args

        def start(self):
            self.target(*self.args)

    module = types.ModuleType("cmf_dev_studio.llm.gemini")
    module.GeminiClient = lambda: None
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(workspaces, "Orchestrator", FakeEngine)
    monkeypatch.setattr(workspaces, "Thread", InlineThread)
    client = TestClient(create_app(tmp_path / "data"))
    project = client.post(
        "/api/projects", json={"location": str(tmp_path), "name": "sample"}
    ).json()
    response = client.post(
        f"/api/projects/{project['id']}/proposals",
        json={
            "task": "Fix error",
            "terminal_context": [
                {"id": 1, "name": "Run", "output": "ERROR\npassword=example"}
            ],
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "ready"
    assert "ERROR" in prompts[0][1]
    assert "password=[REDACTED]" in prompts[0][1]
    assert prompts[0][2] == set()
