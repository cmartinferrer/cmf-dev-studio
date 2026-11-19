"""Recommendation policy preserves requested work without unsolicited advice chains."""

import json

import pytest

from cmf_dev_studio.agents.investigator import Investigator
from cmf_dev_studio.contracts import Plan
from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.recommendations import RecommendationPolicy


class Model:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return json.dumps(self.response)


@pytest.mark.parametrize(
    "history,expected", [([], False), ([{"recommendation": "Extract main"}], True)]
)
def test_investigator_resolves_historical_advice(history, expected):
    """Only a patch tied to available historical advice activates the policy."""
    model = Model(
        {
            "action": "patch",
            "query": "",
            "message": "Extract main",
            "applying_recommendation": True,
        }
    )
    agent = Investigator(model, {}, {}, True, lambda *_: None)
    agent.run("Apply your suggestion", "", "English", history)
    assert agent.applying_recommendation is expected


@pytest.mark.parametrize("quick", [True, False])
@pytest.mark.parametrize(
    "severity,expected", [("none", []), ("critical", ["Data loss risk"]), (None, [])]
)
def test_followup_review_only_reports_critical(monkeypatch, quick, severity, expected):
    """Both patch routes suppress ordinary advice and preserve critical findings."""
    model = Model(
        {
            "recommendation": "More tests",
            "critical": "Data loss risk" if severity == "critical" else "",
        }
    )
    optional, critical = [], []
    engine = Orchestrator(
        model,
        independent_recommendations=True,
        on_recommendation=optional.append,
        on_critical_recommendation=critical.append,
    )
    engine.recommendation_policy = RecommendationPolicy(True)
    operations = [{"action": "create", "path": "calc.py", "content": "pass"}]
    monkeypatch.setattr(engine, "generate_patch", lambda *a, **kw: operations)
    monkeypatch.setattr(engine, "review_patch", lambda *a, **kw: [])
    assert (
        engine.reviewed_patch(
            "Apply advice",
            "prompt",
            Plan((), ()),
            {},
            set(),
            lambda _: None,
            lambda _: None,
            quick=quick,
        )
        == operations
    )
    assert optional == []
    assert critical == expected
    assert len(model.prompts) == 1
    assert "Critical-only" in model.prompts[0]


def test_mixed_intent_preserves_historical_policy():
    """Mixed work activates critical-only review even with a conflicting flag."""
    model = Model(
        {
            "action": "patch",
            "query": "",
            "message": "Apply advice and test another function",
            "applying_recommendation": False,
            "request_intent": "mixed",
        }
    )
    agent = Investigator(model, {}, {}, True, lambda *_: None)
    agent.run(
        "Apply advice and add tests",
        "",
        "English",
        [{"recommendation": "Extract main"}],
    )
    assert agent.applying_recommendation
    assert "read the actual implementation under test" in model.prompts[0]


@pytest.mark.parametrize("critical_only", [False, True])
def test_review_separates_findings_and_records_activity(monkeypatch, critical_only):
    """Review authorized dependencies and filter optional findings in Python."""
    model = Model({"recommendation": "More tests", "critical": "Unsafe evaluation"})
    optional, critical, stages = [], [], []
    engine = Orchestrator(
        model,
        independent_recommendations=True,
        on_recommendation=optional.append,
        on_critical_recommendation=critical.append,
    )
    engine.recommendation_policy = RecommendationPolicy(critical_only)
    operations = [
        {"action": "modify", "path": "test_calc.py", "content": "assert True"}
    ]
    monkeypatch.setattr(engine, "generate_patch", lambda *a, **kw: operations)
    engine.reviewed_patch(
        "Add tests",
        "prompt",
        Plan((), ()),
        {"calc.py": b"def evaluate(x): return eval(x)", "private.py": b"hidden_marker"},
        {"calc.py"},
        lambda _: None,
        stages.append,
        quick=True,
    )
    assert "return eval(x)" in model.prompts[0]
    assert "hidden_marker" not in model.prompts[0]
    assert critical == ["Unsafe evaluation"]
    assert optional == ([] if critical_only else ["More tests"])
    assert stages[-2:] == [
        "recommendation_critical_only" if critical_only else "recommendation_full",
        "recommendation_result_critical",
    ]


def test_critical_event_survives_existing_optional_advice(tmp_path, monkeypatch):
    """An optional event from an earlier attempt cannot hide a critical finding."""
    from cmf_dev_studio import workspaces
    from cmf_dev_studio.projects.manager import ProjectManager
    from cmf_dev_studio.workspaces import WorkspaceService

    class IdleThread:
        def __init__(self, **kwargs):
            pass

        def start(self):
            pass

    monkeypatch.setattr(workspaces, "Thread", IdleThread)
    manager = ProjectManager(tmp_path / "data")
    project = manager.create("sample", location=tmp_path)
    service = WorkspaceService(manager)
    proposal = service.submit(project.id, "Change", [])
    pid = proposal["id"]
    service._record_recommendation(pid, "Optional")
    service._record_recommendation(pid, "Critical", critical=True)
    service._record_recommendation(pid, "Duplicate", critical=True)
    events = [
        e for e in service.get(pid)["events"] if e["kind"] == "assistant_recommendation"
    ]
    assert [e["details"]["message"] for e in events] == ["Optional", "Critical"]
