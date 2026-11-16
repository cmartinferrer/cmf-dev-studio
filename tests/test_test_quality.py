"""Regression tests for shared test-quality instructions and review feedback."""

import json
from unittest.mock import Mock

from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.workflow import test_quality_guidance as quality_guidance


def test_quality_policy_is_shared_by_all_roles_and_repairs():
    """All roles receive the same policy, including a bounded repair after QA rejection."""
    llm = Mock()
    plan = {"requirements": ["Poll repeatedly"], "acceptance": ["Multiple polls occur"]}
    first = [
        {"action": "create", "path": "test_app.py", "content": "def test_poll(): pass"}
    ]
    revised = [
        {
            "action": "create",
            "path": "test_app.py",
            "content": "def test_poll():\n    assert poll_twice() == 2",
        }
    ]
    llm.generate.side_effect = [
        json.dumps(plan),
        json.dumps({"operations": first}),
        '{"issues":["Test does not verify repetition"]}',
        json.dumps({"operations": revised}),
        '{"issues":[]}',
    ]
    result = Orchestrator(llm).prepare(
        "Poll repeatedly", "", "", ["Python"], {}, set(), Mock(), Mock(), Mock()
    )
    assert result == revised
    prompts = [call.args[0] for call in llm.generate.call_args_list]
    assert len(prompts) == 5
    assert all(quality_guidance() in prompt for prompt in prompts)
    assert "Test does not verify repetition" in prompts[3]
    assert "Multiple polls occur" in prompts[3]
    assert "actionable issues" in prompts[4]


def test_quality_policy_covers_observed_regressions():
    """Guard the concrete quality rules identified in generated test reviews."""
    guidance = quality_guidance()
    for rule in (
        "multiple iterations",
        "arguments, counts and order",
        "temporary resources",
        "restore global state",
        "actual values",
        "network calls",
        "preserve valid assertions",
        "smallest sufficient suite",
    ):
        assert rule in guidance
