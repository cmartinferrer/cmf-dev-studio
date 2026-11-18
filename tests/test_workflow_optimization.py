"""Regression tests for bounded generation and review scheduling."""

import json
from unittest.mock import Mock

import pytest

from cmf_dev_studio.contracts import Plan
from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.workspaces import validate_operations


def test_structural_and_review_failures_share_attempt_budget():
    """A rejected patch and malformed responses consume the same budget."""
    llm = Mock()
    valid = json.dumps(
        {"operations": [{"action": "create", "path": "app.py", "content": "x = 1\n"}]}
    )
    llm.generate.side_effect = [
        "invalid",
        valid,
        '{"issues":["missing tests"]}',
        "invalid",
    ]
    engine = Orchestrator(llm)
    with pytest.raises(ValueError, match="Could not generate a safe patch"):
        engine.reviewed_patch(
            "task",
            "prompt",
            Plan(("task",), ("criterion",)),
            {},
            set(),
            lambda ops: validate_operations(ops, {}, set()),
            Mock(),
        )
    assert llm.generate.call_count == 4
    assert "Structural validation" in llm.generate.call_args_list[1].args[0]
    assert "missing tests" in llm.generate.call_args_list[3].args[0]


def test_provider_failure_is_not_retried_by_orchestrator():
    """Infrastructure failures propagate to the explicit retry workflow."""
    llm = Mock()
    llm.generate.side_effect = RuntimeError("provider unavailable")
    engine = Orchestrator(llm)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        engine.reviewed_patch(
            "task", "prompt", Plan(("task",), ()), {}, set(), Mock(), Mock()
        )
    assert llm.generate.call_count == 1


@pytest.mark.parametrize("allowed", [True, False])
def test_repair_expands_context_only_with_existing_permission(
    tmp_path, monkeypatch, allowed
):
    """Repair reads the immutable baseline only with existing exploration approval."""
    import sys
    from types import SimpleNamespace

    from cmf_dev_studio import workspaces
    from cmf_dev_studio.projects.manager import ProjectManager

    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = workspaces.WorkspaceService(manager)
    pid = "repair"
    original = {"helper.py": b"value = 1\n"}
    baseline = service.baselines / pid
    baseline.mkdir()
    (baseline / "helper.py").write_bytes(original["helper.py"])
    (service.root / pid).mkdir()
    current = [{"action": "create", "path": "app.py", "content": "x = 1\n"}]
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at,assistant_language) VALUES (?,?,?,?,?,?)",
            (pid, project.id, "test_failed", "fix", "now", "English"),
        )
        if allowed:
            service._event(db, pid, "exploration_allowed")
    service._update(
        pid, "test_failed", changes=service._write_operations(pid, current, original)
    )
    replacement = current + [
        {"action": "modify", "path": "helper.py", "content": "value = 2\n"}
    ]
    llm = Mock()
    llm.generate.side_effect = [json.dumps({"operations": replacement})] * 2 + [
        '{"issues":[]}'
    ]
    monkeypatch.setitem(
        sys.modules,
        "cmf_dev_studio.llm.gemini",
        SimpleNamespace(GeminiClient=lambda: llm),
    )
    service._repair(pid, service.get(pid), original, current)
    row = service.get(pid)
    assert row["status"] == ("ready" if allowed else "test_failed")
    assert ("helper.py" in row["approved_paths"]) is allowed
    assert any(e["kind"] == "exploration_tool" for e in row["events"]) is allowed
    if allowed:
        assert "FILE: helper.py\nvalue = 1" in llm.generate.call_args_list[1].args[0]
    else:
        assert all(
            "FILE: helper.py\nvalue = 1" not in call.args[0]
            for call in llm.generate.call_args_list
        )
