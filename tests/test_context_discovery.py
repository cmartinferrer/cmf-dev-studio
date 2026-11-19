"""Exercise late context discovery through the real proposal API and agents."""

import json
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cmf_dev_studio import workspaces
from cmf_dev_studio.api.app import create_app
from cmf_dev_studio.projects.intelligence import prepare_context


@pytest.mark.parametrize("decision", [True, False, None, "sensitive"])
def test_late_context_discovery(tmp_path, monkeypatch, decision):
    """Pause for permission, reuse a grant, or stop without exposing source."""
    prompts = []
    operations = [
        {"action": "modify", "path": "test_calc.py", "content": "assert True\n"}
    ]

    class Model:
        def generate(self, prompt):
            prompts.append(prompt)
            if "ROLE: RECOMMENDATION" in prompt:
                return json.dumps({"recommendation": "", "critical": ""})
            if "FINAL OUTPUT CONTRACT" in prompt:
                return json.dumps({"operations": operations})
            if decision is None and '"exploration_allowed": false' in prompt:
                return json.dumps(
                    {"action": "permission", "query": "", "message": "Explore?"}
                )
            return json.dumps(
                {"action": "quick_patch", "query": "", "message": "Fix tests"}
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
    (root / "calc.py").write_text("def add(a, b): return a + b\n")
    test = root / "test_calc.py"
    original_test = (
        'password = "actual-secret-value"\n'
        if decision == "sensitive"
        else "# unique test marker\n"
    )
    test.write_text(original_test)
    context = prepare_context(root, ["calc.py"])
    row = client.post(
        f"/api/projects/{project['id']}/proposals",
        json={
            "task": "Fix tests",
            "assistant_language": "English",
            "context_paths": ["calc.py"],
            "context_digest": context["digest"],
        },
    ).json()
    assert row["status"] == "awaiting_exploration", row
    assert all("unique test marker" not in p for p in prompts)
    row = client.post(
        f"/api/proposals/{row['id']}/exploration-decision",
        json={"allow": decision is not False},
    ).json()
    assert test.read_text() == original_test
    if decision == "sensitive":
        assert row["status"] == "failed"
        assert "test_calc.py" not in row["approved_paths"]
        assert all("actual-secret-value" not in p for p in prompts)
        return
    if decision is False:
        assert row["status"] == "answered"
        assert all("unique test marker" not in p for p in prompts)
    else:
        assert row["status"] == "ready", row
        assert "test_calc.py" in row["approved_paths"]
        developer_prompts = [p for p in prompts if "FINAL OUTPUT CONTRACT" in p]
        assert "unique test marker" in developer_prompts[-1]
        assert sum(e["kind"] == "exploration_allowed" for e in row["events"]) == 1
        assert sum("FINAL OUTPUT CONTRACT" in p for p in prompts) == 2
