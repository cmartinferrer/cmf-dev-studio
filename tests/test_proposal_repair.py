"""Regression tests for explicit repair and multiline source preservation."""

import json
from unittest.mock import Mock

import pytest

import cmf_dev_studio.workspaces as module
from cmf_dev_studio.contracts import parse_json
from cmf_dev_studio.projects.manager import ProjectManager
from cmf_dev_studio.workspaces import WorkspaceError, WorkspaceService


def test_multiline_roundtrip(tmp_path):
    """Preserve source newlines through JSON, storage and preview."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample")
    service = WorkspaceService(manager)
    pid = "sample"
    (service.root / pid).mkdir()
    content = "public class Calculator {\n    int add(int a, int b) {\n        return a + b;\n    }\n}\n"
    ops = parse_json(
        json.dumps(
            {
                "operations": [
                    {"action": "create", "path": "Calculator.java", "content": content}
                ]
            }
        )
    )["operations"]
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "queued", "task", "now"),
        )
    service._update(pid, "ready", changes=service._write_operations(pid, ops, {}))
    assert service.preview_file(pid, "Calculator.java")["after"] == content
    assert (service.root / pid / "Calculator.java").read_bytes() == content.encode()


def test_repair_requires_fresh_approval(tmp_path, monkeypatch):
    """Repair keeps history, never runs tests, and invalidates old tokens."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample")
    service = WorkspaceService(manager)
    pid = "sample"
    (service.root / pid).mkdir()
    (service.baselines / pid).mkdir()
    ops = [
        {
            "action": "create",
            "path": "test_sample.py",
            "content": "def test_sample():\n    assert False\n",
        }
    ]
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "queued", "task", "now"),
        )
    service._update(pid, "ready", changes=service._write_operations(pid, ops, {}))
    runner = Mock(return_value=(False, "failure"))
    monkeypatch.setattr(module, "execute_runner", runner)
    service.test(pid, service.test_preview(pid)["approval"])
    with pytest.raises(WorkspaceError, match="Repair the failed patch"):
        service.test_preview(pid)
    old = "stale-token"
    engine = Mock()
    fixed = [{**ops[0], "content": "def test_sample():\n    assert True\n"}]
    engine.reviewed_patch.return_value = fixed
    monkeypatch.setattr(module, "Orchestrator", lambda _: engine)
    import sys
    import types

    monkeypatch.setitem(
        sys.modules,
        "cmf_dev_studio.llm.gemini",
        types.SimpleNamespace(GeminiClient=lambda: None),
    )

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(module, "Thread", ImmediateThread)
    assert service.repair(pid)["status"] == "ready"
    assert runner.call_count == 1
    assert service.preview_file(pid, "test_sample.py")["after"] == fixed[0]["content"]
    assert "failure" == engine.reviewed_patch.call_args.kwargs["feedback"]
    assert [e["kind"] for e in service.get(pid)["events"]][-2:] == [
        "repair_requested",
        "repair_ready",
    ]
    with pytest.raises(WorkspaceError, match="Explicit approval"):
        service.test(pid, old)
    with pytest.raises(WorkspaceError, match="Only failed"):
        service.repair(pid)

    # A failed repair must retain the previous patch and its test result.
    runner.return_value = (False, "second failure")
    service.test(pid, service.test_preview(pid)["approval"])
    engine.reviewed_patch.side_effect = ValueError("invalid repair")
    assert service.repair(pid)["status"] == "test_failed"
    assert service.preview_file(pid, "test_sample.py")["after"] == fixed[0]["content"]
    assert service.get(pid)["test_output"] == "second failure"
    assert service.get(pid)["events"][-1]["kind"] == "repair_failed"
    assert runner.call_count == 2


def test_unchanged_repair_and_limit(tmp_path, monkeypatch):
    """Reject unchanged patches and stop after three persisted repair requests."""
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample")
    service = WorkspaceService(manager)
    pid = "sample"
    (service.root / pid).mkdir()
    (service.baselines / pid).mkdir()
    ops = [
        {
            "action": "create",
            "path": "test_sample.py",
            "content": "def test_sample():\n    assert False\n",
        }
    ]
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at) VALUES (?,?,?,?,?)",
            (pid, project.id, "queued", "task", "now"),
        )
    service._update(pid, "ready", changes=service._write_operations(pid, ops, {}))
    runner = Mock(return_value=(False, "AssertionError"))
    monkeypatch.setattr(module, "execute_runner", runner)
    service.test(pid, service.test_preview(pid)["approval"])
    engine = Mock()
    engine.reviewed_patch.return_value = ops
    monkeypatch.setattr(module, "Orchestrator", lambda _: engine)
    import sys
    import types

    monkeypatch.setitem(
        sys.modules,
        "cmf_dev_studio.llm.gemini",
        types.SimpleNamespace(GeminiClient=lambda: None),
    )

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(module, "Thread", ImmediateThread)
    for _ in range(3):
        assert service.repair(pid)["status"] == "test_failed"
        assert "did not change" in service.get(pid)["error"]
    with pytest.raises(WorkspaceError, match="Repair limit"):
        WorkspaceService(manager).repair(pid)
    with pytest.raises(WorkspaceError, match="Repair the failed patch"):
        service.test_preview(pid)
    assert runner.call_count == 1
    assert service.preview_file(pid, "test_sample.py")["after"] == ops[0]["content"]
