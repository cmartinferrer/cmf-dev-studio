"""Independent recommendation review and orchestration tests."""

import json

import pytest

from cmf_dev_studio.agents.recommendation import RecommendationAgent
from cmf_dev_studio.contracts import Plan
from cmf_dev_studio.orchestrator import Orchestrator


class Model:
    def __init__(self, fail=False):
        self.fail = fail
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("Unavailable")
        return json.dumps(
            {
                "recommendation": "Rename multiplicar to multiply in calc.py",
                "critical": "",
            }
        )


@pytest.mark.parametrize("quick", [True, False])
def test_independent_review_runs_even_without_candidates(monkeypatch, quick):
    """Both workflows independently review the accepted patch."""
    model = Model()
    published = []
    engine = Orchestrator(
        model, on_recommendation=published.append, independent_recommendations=True
    )
    operations = [
        {"action": "modify", "path": "calc.py", "content": "def multiplicar(): pass"}
    ]
    monkeypatch.setattr(engine, "generate_patch", lambda *a, **kw: operations)
    monkeypatch.setattr(engine, "review_patch", lambda *a, **kw: [])
    result = engine.reviewed_patch(
        "Add negate",
        "prompt",
        Plan((), ()),
        {"secret": b"private"},
        set(),
        lambda _: None,
        lambda _: None,
        quick=quick,
    )
    assert result == operations
    assert len(model.prompts) == 1
    assert "multiplicar" in model.prompts[0]
    assert "private" not in model.prompts[0]
    assert published == ["Rename multiplicar to multiply in calc.py"]


def test_failure_is_nonblocking():
    """Provider failures do not invalidate the requested change."""
    agent = RecommendationAgent(Model(fail=True))
    assert agent.review("task", Plan((), ()), [], {}, set(), []).status == "failed"


def test_deleted_file_is_not_reviewed():
    """Review uses final content, not deleted or unapproved source."""
    model = Model()
    RecommendationAgent(model).review(
        "task",
        Plan((), ()),
        [{"action": "delete", "path": "old.py"}],
        {"old.py": b"obsolete_marker", "other.py": b"hidden_marker"},
        {"old.py"},
        [],
    )
    assert "obsolete_marker" not in model.prompts[0]
    assert "hidden_marker" not in model.prompts[0]


def test_critical_review_keeps_skills_and_inspects_final_entry_points():
    """Keep skill guidance and independent security checks in critical-only mode."""
    from cmf_dev_studio.skills.registry import SkillContext

    activity = []
    model = Model()
    agent = RecommendationAgent(
        model, skills=SkillContext(activity=lambda *args: activity.append(args))
    )
    result = agent.review(
        "Apply previous advice",
        Plan((), ()),
        [{"action": "modify", "path": "cli.py", "content": "evaluate(user_input)"}],
        {"calc.py": b"def evaluate(x): return eval(x)", "secret.py": b"private_marker"},
        {"calc.py"},
        [],
        critical_only=True,
    )
    assert len(model.prompts) == 1
    prompt = model.prompts[0]
    assert "return eval(x)" in prompt
    assert "evaluate(user_input)" in prompt
    assert "private_marker" not in prompt
    assert "dynamic code" in prompt
    assert "suppress optional advice only" in prompt
    assert any(role == "recommendation" for role, _ in activity)
    assert result.optional == ""
