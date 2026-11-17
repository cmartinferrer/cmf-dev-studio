"""Verify adaptive routing and bounded review with a simulated model."""

import json
from unittest.mock import Mock

from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.workspaces import validate_operations


def test_quick_patch_uses_only_developer():
    """A known local correction does not require planning or generated tests."""
    llm = Mock()
    original = {"Main.java": b"class Main {}"}
    operations = [
        {
            "action": "modify",
            "path": "Main.java",
            "content": "class Main { int n = 1; }",
        }
    ]
    llm.generate.return_value = json.dumps({"operations": operations})
    stages = []
    result = Orchestrator(llm).prepare(
        "fix",
        "Main.java",
        "class Main {}",
        ["Java"],
        original,
        {"Main.java"},
        lambda ops: validate_operations(ops, original, {"Main.java"}),
        stages.append,
        Mock(),
        quick=True,
        diagnosis="Known local error",
    )
    assert result == operations
    assert stages == ["developer"]
    assert llm.generate.call_count == 1
    assert "Add a regression test only if needed" in llm.generate.call_args.args[0]


def test_review_repair_receives_previous_patch():
    """The developer can correct the exact rejected implementation."""
    llm = Mock()
    first = [{"action": "create", "path": "a.py", "content": "bad_candidate = 1"}]
    second = [{"action": "create", "path": "a.py", "content": "good_candidate = 2"}]
    llm.generate.side_effect = [
        json.dumps({"requirements": ["feature"], "acceptance": ["result"]}),
        json.dumps({"operations": first}),
        json.dumps({"issues": ["Fix the test"]}),
        json.dumps({"operations": second}),
        json.dumps({"issues": []}),
    ]
    result = Orchestrator(llm).prepare(
        "feature",
        "",
        "",
        ["Python"],
        {},
        set(),
        Mock(),
        Mock(),
        Mock(),
    )
    assert result == second
    prompt = llm.generate.call_args_list[3].args[0]
    assert "bad_candidate = 1" in prompt
    assert "Fix the test" in prompt
