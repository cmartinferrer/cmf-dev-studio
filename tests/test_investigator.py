"""Exercise the investigation loop without calling a remote model."""

import json

from cmf_dev_studio.agents.investigator import MAX_ROUNDS, Investigator


class Model:
    def __init__(self, actions):
        self.actions = iter(actions)
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        action, query, message = next(self.actions)
        return json.dumps({"action": action, "query": query, "message": message})


def test_permission_before_read():
    """A tool request must pause before disclosing source."""
    model = Model([("read", "Hola.java", "")])
    agent = Investigator(model, {"Hola.java": b"asdf"}, {}, False, lambda *_: None)
    assert agent.run("fix", [], "Spanish", [])[0] == "permission"
    assert not agent.approved
    assert "asdf" not in model.prompts[0]


def test_search_and_read_then_patch():
    """A pasted log can drive discovery without attached files."""
    model = Model(
        [
            ("find", "Hola.java", ""),
            ("read", "src/Hola.java", ""),
            ("patch", "", "Syntax error"),
        ]
    )
    agent = Investigator(model, {"src/Hola.java": b"asdf"}, {}, True, lambda *_: None)
    assert agent.run("fix Hola.java", [], "English", []) == ("patch", "Syntax error")
    assert agent.approved == {"src/Hola.java": "asdf"}
    assert "asdf" in model.prompts[-1]


def test_answer_without_exploration():
    """An explanation does not require a patch or permission."""
    agent = Investigator(
        Model([("answer", "", "Explanation")]), {}, {}, False, lambda *_: None
    )
    assert agent.run("why?", [], "English", [])[0] == "answer"


def test_sensitive_and_external_paths():
    """Search and read cannot expose excluded source or credentials."""
    agent = Investigator(
        None,
        {
            "src/a.py": b'password = "actual-secret-value"',
            ".env": b"abc",
            "src/b.py": b"hello",
        },
        {},
        True,
        lambda *_: None,
    )
    assert agent.tool("read", "../outside.py") == "File unavailable or excluded."
    assert agent.tool("read", "src/a.py") == "File unavailable or excluded."
    assert agent.tool("read", ".env") == "File unavailable or excluded."
    assert json.loads(agent.tool("search", "actual-secret-value")) == []
    assert json.loads(agent.tool("search", "hello")) == ["src/b.py:1"]


def test_bounded_loop():
    """Repeated tool calls terminate in a clarification."""
    agent = Investigator(
        Model([("find", "missing", "")] * 8), {}, {}, True, lambda *_: None
    )
    assert agent.run("fix", [], "Spanish", [])[0] == "question"


def test_api_permission_and_patch(tmp_path, monkeypatch):
    """Resume the same request and grant patch access only to inspected files."""
    import sys
    import types

    from fastapi.testclient import TestClient

    from cmf_dev_studio import workspaces
    from cmf_dev_studio.api.app import create_app

    model = Model(
        [
            ("find", "Hola.java", "Necesito localizar el fichero."),
            ("find", "Hola.java", ""),
            ("read", "Hola.java", ""),
            ("quick_patch", "", "El fichero no contiene una clase válida."),
        ]
    )
    module = types.ModuleType("cmf_dev_studio.llm.gemini")
    module.GeminiClient = lambda: model
    monkeypatch.setitem(sys.modules, module.__name__, module)

    class InlineThread:
        def __init__(self, target, args, daemon):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    attempts = []

    class Engine:
        def __init__(
            self,
            client,
            *,
            on_recommendation=None,
            independent_recommendations=False,
            skills=None,
            on_critical_recommendation=None,
        ):
            assert independent_recommendations is True

        def prepare(
            self,
            task,
            inventory,
            approved,
            languages,
            original,
            approved_paths,
            validate,
            stage,
            save_plan,
            **options,
        ):
            assert approved_paths == {"Hola.java"}
            assert "asdf" in approved
            assert options["quick"] is True
            attempts.append(options)
            if len(attempts) == 1:
                raise ValueError("temporary generation failure")
            ops = [
                {"action": "modify", "path": "Hola.java", "content": "class Hola {}\n"}
            ]
            validate(ops)
            return ops

    monkeypatch.setattr(workspaces, "Thread", InlineThread)
    monkeypatch.setattr(workspaces, "Orchestrator", Engine)
    client = TestClient(create_app(tmp_path / "data"))
    project = client.post(
        "/api/projects", json={"location": str(tmp_path), "name": "sample"}
    ).json()
    from pathlib import Path

    source = Path(project["path"]) / "Hola.java"
    source.write_text("asdf")
    row = client.post(
        f"/api/projects/{project['id']}/proposals",
        json={
            "task": "Corrige Hola.java",
            "assistant_language": "Spanish",
        },
    ).json()
    assert row["status"] == "awaiting_exploration"
    assert row["approved_paths"] == []
    assert any(
        e["kind"] == "skill_selected" and e["details"]["stage"] == "investigator"
        for e in row["events"]
    )
    result = client.post(
        f"/api/proposals/{row['id']}/exploration-decision", json={"allow": True}
    ).json()
    assert result["status"] == "failed"
    result = client.post(
        f"/api/proposals/{row['id']}/generation-decision", json={"retry": True}
    ).json()
    assert result["status"] == "ready"
    assert "temporary generation failure" in attempts[1]["feedback"]
    assert len(model.prompts) == 4
    assert result["approved_paths"] == ["Hola.java"]
    assert source.read_text() == "asdf"
    assert any(e["kind"] == "assistant_response" for e in result["events"])


def test_permission_question_is_normalized_and_grant_is_not_repeated():
    """A model cannot turn exploration authorization into a conversational loop."""
    question = "¿Autorizas permisos para explorar el proyecto?"
    model = Model([("question", "", question)])
    agent = Investigator(model, {}, {}, False, lambda *_: None)
    assert agent.run("create", [], "Spanish", [])[0] == "permission"
    model = Model(
        [
            ("permission", "", question),
            ("question", "", question),
            ("patch", "", "Create a file"),
        ]
    )
    agent = Investigator(model, {}, {}, True, lambda *_: None)
    assert agent.run("create", [], "Spanish", [])[0] == "patch"
    assert "Already authorized" in model.prompts[-1]


def test_invalid_tool_request_recovers():
    """Correct invalid requests within the existing investigation budget."""
    model = Model(
        [
            ("read", "", ""),
            ("unknown", "a.py", ""),
            ("search", "x" * 301, ""),
            ("read", "a.py", ""),
            ("patch", "", "Fix"),
        ]
    )
    agent = Investigator(model, {"a.py": b"hello"}, {}, True, lambda *_: None)
    assert agent.run("fix", [], "English", []) == ("patch", "Fix")
    assert '"code": "invalid_query"' in model.prompts[1]
    assert '"code": "unknown_tool"' in model.prompts[2]
    assert agent.approved == {"a.py": "hello"}


def test_invalid_tool_requests_are_bounded():
    """Repeated invalid calls cannot loop indefinitely."""
    model = Model([("read", "", "")] * MAX_ROUNDS)
    agent = Investigator(model, {}, {}, True, lambda *_: None)
    assert agent.run("fix", [], "English", [])[0] == "question"
    assert len(model.prompts) == MAX_ROUNDS


def test_followup_receives_historical_recommendation():
    """Expose prior advice without granting access to current source files."""
    advice = "Refactor CLI using a dispatcher dictionary."
    model = Model([("permission", "", "May I inspect the CLI?")])
    agent = Investigator(
        model, {"calc.py": b"current source"}, {}, False, lambda *_: None
    )
    history = [
        {
            "task": "Add maximum",
            "response": "",
            "snapshot_unchanged": False,
            "recommendation": advice,
            "outcome": "applied",
        }
    ]
    assert agent.run("Apply your advice", [], "English", history)[0] == "permission"
    assert advice in model.prompts[0]
    assert "current source" not in model.prompts[0]
