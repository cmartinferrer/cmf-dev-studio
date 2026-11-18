"""Verify shared code-awareness instructions reach every agent."""

import json
from unittest.mock import Mock

from cmf_dev_studio.agents.investigator import Investigator
from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.workflow import code_awareness_guidance


def test_code_awareness_across_patch_roles():
    """Planning, generation and review share evidence and scope constraints."""
    llm = Mock()
    llm.generate.side_effect = [
        json.dumps({"requirements": ["Rename add"], "acceptance": ["Calls work"]}),
        json.dumps({"operations": []}),
        json.dumps({"issues": []}),
    ]
    engine = Orchestrator(llm)
    plan = engine.plan_patch("Rename add", "Main.java", "class Main {}", ["Java"])
    operations = engine.generate_patch("Task", plan, validate=lambda _: None)
    engine.review_patch("Rename add", plan, operations)
    assert llm.generate.call_count == 3
    for call in llm.generate.call_args_list:
        assert code_awareness_guidance() in call.args[0]


def test_investigator_reference_discovery():
    """Reference search uses the existing permission and approved snapshot."""
    llm = Mock()
    llm.generate.side_effect = [
        json.dumps({"action": "search", "query": "sumar", "message": ""}),
        json.dumps({"action": "read", "query": "test_calc.py", "message": ""}),
        json.dumps({"action": "patch", "query": "", "message": "Rename and update"}),
    ]
    agent = Investigator(
        llm,
        {
            "calc.py": b"def sumar(a, b): return a+b",
            "test_calc.py": b"from calc import sumar",
        },
        {"calc.py": "def sumar(a, b): return a+b"},
        True,
        lambda *_: None,
    )
    assert agent.run("Rename sumar to add", [], "English", [])[0] == "patch"
    assert agent.approved["test_calc.py"] == "from calc import sumar"
    assert "test_calc.py:1" in llm.generate.call_args_list[1].args[0]
    assert code_awareness_guidance() in llm.generate.call_args_list[0].args[0]
