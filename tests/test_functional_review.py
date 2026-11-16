"""Regression contracts for requirement-driven functional review."""

import json
from unittest.mock import Mock

import pytest

from cmf_dev_studio.contracts import Plan
from cmf_dev_studio.orchestrator import Orchestrator


@pytest.mark.parametrize(
    "response",
    [
        "{}",
        '{"requirements":["feature"],"acceptance":[]}',
        '{"requirements":"feature","acceptance":["works"]}',
    ],
)
def test_invalid_plan_blocks_generation(response):
    """Never proceed to development without a valid acceptance plan."""
    llm = Mock()
    llm.generate.return_value = response
    with pytest.raises(ValueError, match="Analyst"):
        Orchestrator(llm).prepare(
            "feature", "", "", [], {}, set(), Mock(), Mock(), Mock()
        )
    assert llm.generate.call_count == 1


@pytest.mark.parametrize("response", ["{}", '{"issues":[" "]}'])
def test_invalid_review_blocks_even_legacy_plan(response):
    """Malformed QA responses cannot silently approve a patch."""
    llm = Mock()
    llm.generate.return_value = response
    with pytest.raises(ValueError, match="valid structured review"):
        Orchestrator(llm).review_patch("feature", Plan(("feature",), ()), [])


def test_functional_issue_is_sent_back_to_developer():
    """A mocked QA rejection of a placeholder triggers a bounded revision."""
    llm = Mock()
    plan = {
        "requirements": ["Persist records"],
        "acceptance": ["Record survives reopening"],
    }
    bad = [
        {
            "action": "create",
            "path": "app.py",
            "content": "def save(record): print(record)",
        }
    ]
    good = [
        {
            "action": "create",
            "path": "app.py",
            "content": 'def save(record):\n    with open("records.txt", "a") as f:\n        f.write(record + "\\n")',
        }
    ]
    llm.generate.side_effect = [
        json.dumps(plan),
        json.dumps({"operations": bad}),
        json.dumps({"issues": ["Logging does not persist records"]}),
        json.dumps({"operations": good}),
        '{"issues":[]}',
    ]
    engine = Orchestrator(llm)
    assert (
        engine.prepare(
            "Persist records", "", "", ["Python"], {}, set(), Mock(), Mock(), Mock()
        )
        == good
    )
    prompts = [call.args[0] for call in llm.generate.call_args_list]
    assert "Requirements:\nPersist records" in prompts[2]
    assert "Passing tests alone" in prompts[2]
    assert "Logging does not persist records" in prompts[3]
    assert "Never remove required behavior" in prompts[3]
    assert "Record survives reopening" in prompts[3]
    assert llm.generate.call_count == 5
