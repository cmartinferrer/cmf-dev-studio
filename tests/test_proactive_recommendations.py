"""Optional recommendations remain separate from the requested patch."""

import json
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cmf_dev_studio import workspaces
from cmf_dev_studio.api.app import create_app
from cmf_dev_studio.projects.intelligence import prepare_context


@pytest.mark.parametrize(
    "suggestion", ["Rename sumar to add for consistency", "", None, 42]
)
def test_investigator_advice_is_not_published_before_patch(
    tmp_path, monkeypatch, suggestion
):
    """Pass preliminary advice as data without publishing unreviewed advice."""
    prompts = []

    class Model:
        def generate(self, prompt):
            prompts.append(prompt)
            if "ROLE: RECOMMENDATION" in prompt:
                return json.dumps({"recommendation": "", "critical": ""})
            if "FINAL OUTPUT CONTRACT" in prompt:
                return json.dumps(
                    {
                        "operations": [
                            {
                                "action": "modify",
                                "path": "calc.py",
                                "content": "def sumar(a,b): return a+b\ndef subtract(a,b): return a-b\n",
                            }
                        ]
                    }
                )
            return json.dumps(
                {
                    "action": "quick_patch",
                    "query": "",
                    "message": "Add subtract",
                    "recommendation": suggestion,
                }
            )

    module = types.ModuleType("cmf_dev_studio.llm.gemini")
    module.GeminiClient = Model
    monkeypatch.setitem(sys.modules, module.__name__, module)

    class InlineThread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(workspaces, "Thread", InlineThread)
    client = TestClient(create_app(tmp_path / "data"))
    project = client.post(
        "/api/projects", json={"location": str(tmp_path), "name": "sample"}
    ).json()
    root = Path(project["path"])
    source = root / "calc.py"
    original = "def sumar(a,b): return a+b\n"
    source.write_text(original)
    context = prepare_context(root, ["calc.py"])
    row = client.post(
        f"/api/projects/{project['id']}/proposals",
        json={
            "task": "Add subtract",
            "assistant_language": "English",
            "context_paths": ["calc.py"],
            "context_digest": context["digest"],
        },
    ).json()
    assert row["status"] == "ready", row
    assert not any(e["kind"] == "assistant_response" for e in row["events"])
    handoff = next(e for e in row["events"] if e["kind"] == "investigation_completed")
    assert handoff["details"]["message"]
    events = [e for e in row["events"] if e["kind"] == "assistant_recommendation"]
    assert not events
    if isinstance(suggestion, str) and suggestion:
        assert suggestion in prompts[-1]
    assert len(prompts) == 3
    assert source.read_text() == original
    assert [change["path"] for change in row["changes"]] == ["calc.py"]


@pytest.mark.parametrize(
    "role",
    ["developer", "tester", "both", "quick", "investigator", "investigator_quick"],
)
def test_recommendations_from_patch_roles(tmp_path, monkeypatch, role):
    """Collect optional advice from existing calls, including quick patches."""
    advice = "Rename multiplicar to multiply for consistent naming"
    prompts = []

    class Model:
        def generate(self, prompt):
            prompts.append(prompt)
            if "ROLE: RECOMMENDATION" in prompt:
                return json.dumps(
                    {
                        "recommendation": advice if role != "developer" else "",
                        "critical": "",
                    }
                )
            if "FINAL OUTPUT CONTRACT" in prompt:
                return json.dumps(
                    {
                        "operations": [
                            {
                                "action": "modify",
                                "path": "calc.py",
                                "content": "def multiplicar(a,b): return a*b\ndef add(a,b): return a+b\n",
                            }
                        ],
                        "recommendation": (
                            advice
                            if role
                            in ("developer", "both", "quick", "investigator_quick")
                            else ""
                        ),
                    }
                )
            if "ROLE: TESTER" in prompt:
                return json.dumps(
                    {
                        "issues": [],
                        "recommendation": (
                            advice if role in ("tester", "both", "investigator") else ""
                        ),
                        "recommendation_decision": (
                            "accepted"
                            if role in ("tester", "both", "investigator")
                            else "rejected"
                        ),
                    }
                )
            if "ROLE: ANALYST" in prompt:
                return json.dumps(
                    {"requirements": ["Add add"], "acceptance": ["Addition works"]}
                )
            return json.dumps(
                {
                    "action": (
                        "quick_patch"
                        if role in ("quick", "investigator_quick")
                        else "patch"
                    ),
                    "query": "",
                    "message": "Add addition",
                    "recommendation": advice if role.startswith("investigator") else "",
                }
            )

    module = types.ModuleType("cmf_dev_studio.llm.gemini")
    module.GeminiClient = Model
    monkeypatch.setitem(sys.modules, module.__name__, module)

    class InlineThread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(workspaces, "Thread", InlineThread)
    client = TestClient(create_app(tmp_path / "data"))
    project = client.post(
        "/api/projects", json={"location": str(tmp_path), "name": "sample"}
    ).json()
    root = Path(project["path"])
    source = root / "calc.py"
    original = "def multiplicar(a,b): return a*b\n"
    source.write_text(original)
    context = prepare_context(root, ["calc.py"])
    row = client.post(
        f"/api/projects/{project['id']}/proposals",
        json={
            "task": "Add addition with English naming",
            "assistant_language": "English",
            "context_paths": ["calc.py"],
            "context_digest": context["digest"],
        },
    ).json()
    assert row["status"] == "ready", row
    assert not any(e["kind"] == "assistant_response" for e in row["events"])
    handoff = next(e for e in row["events"] if e["kind"] == "investigation_completed")
    assert handoff["details"]["message"]
    events = [e for e in row["events"] if e["kind"] == "assistant_recommendation"]
    if role == "developer":
        assert not events
    else:
        assert len(events) == 1
        assert events[0]["details"]["message"] == advice
    assert len(prompts) == (3 if role in ("quick", "investigator_quick") else 5)
    if role.startswith("investigator"):
        assert advice in next(p for p in prompts if "FINAL OUTPUT CONTRACT" in p)
        assert advice in prompts[-1]
    else:
        assert all(
            advice not in prompt
            for prompt in prompts
            if "ROLE: TESTER" not in prompt and "ROLE: RECOMMENDATION" not in prompt
        )
    if role in ("developer", "both"):
        assert advice in prompts[-1]
    assert source.read_text() == original


def test_requested_rename_is_not_published_as_optional_advice():
    """The final reviewer can veto advice that duplicates the requested patch."""
    from cmf_dev_studio.contracts import Plan
    from cmf_dev_studio.orchestrator import Orchestrator

    task = "Rename multiplicar to multiply and update all references"
    advice = "Update CLI and tests to use multiply"
    prompts = []
    published = []

    class Model:
        def generate(self, prompt):
            prompts.append(prompt)
            if "ROLE: TESTER" in prompt:
                assert task in prompt
                assert advice in prompt
                assert "Proposed diffs" in prompt
                assert "an empty string vetoes earlier advice" in prompt
                return json.dumps({"issues": [], "recommendation": ""})
            return json.dumps(
                {
                    "operations": [
                        {
                            "action": "modify",
                            "path": "calc.py",
                            "content": "def multiply(a,b): return a*b\n",
                        }
                    ],
                    "recommendation": advice,
                }
            )

    engine = Orchestrator(Model(), on_recommendation=published.append)
    operations = engine.reviewed_patch(
        task,
        task,
        Plan((task,), ("References updated",)),
        {"calc.py": b"def multiplicar(a,b): return a*b\n"},
        {"calc.py"},
        lambda _: None,
        lambda _: None,
    )
    assert "def multiply" in operations[0]["content"]
    assert not any(published)
    assert len(prompts) == 2
