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
def test_recommendation_is_optional_and_not_patch_context(
    tmp_path, monkeypatch, suggestion
):
    """Persist valid advice without adding it to developer instructions or writes."""
    prompts = []

    class Model:
        def generate(self, prompt):
            prompts.append(prompt)
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
    events = [e for e in row["events"] if e["kind"] == "assistant_recommendation"]
    if isinstance(suggestion, str) and suggestion:
        assert len(events) == 1
        assert events[0]["details"]["message"] == suggestion
        assert suggestion not in prompts[-1]
    else:
        assert not events
    assert len(prompts) == 2
    assert source.read_text() == original
    assert [change["path"] for change in row["changes"]] == ["calc.py"]


@pytest.mark.parametrize("role", ["developer", "tester", "both", "quick"])
def test_recommendations_from_patch_roles(tmp_path, monkeypatch, role):
    """Collect optional advice from existing calls, including quick patches."""
    advice = "Rename multiplicar to multiply for consistent naming"
    prompts = []

    class Model:
        def generate(self, prompt):
            prompts.append(prompt)
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
                            advice if role in ("developer", "both", "quick") else ""
                        ),
                    }
                )
            if "ROLE: TESTER" in prompt:
                return json.dumps(
                    {
                        "issues": [],
                        "recommendation": advice if role in ("tester", "both") else "",
                    }
                )
            if "ROLE: ANALYST" in prompt:
                return json.dumps(
                    {"requirements": ["Add add"], "acceptance": ["Addition works"]}
                )
            return json.dumps(
                {
                    "action": "quick_patch" if role == "quick" else "patch",
                    "query": "",
                    "message": "Add addition",
                    "recommendation": "",
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
    events = [e for e in row["events"] if e["kind"] == "assistant_recommendation"]
    assert len(events) == 1
    assert events[0]["details"]["message"] == advice
    assert len(prompts) == (2 if role == "quick" else 4)
    assert all(advice not in prompt for prompt in prompts)
    assert source.read_text() == original
