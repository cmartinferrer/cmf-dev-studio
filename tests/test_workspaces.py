import json
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cmf_dev_studio.api.app import create_app
from cmf_dev_studio.workspaces import WorkspaceError, safe_path, snapshot


@pytest.mark.parametrize(
    "path",
    [
        "../secret.py",
        "/tmp/x.py",
        ".env",
        "src/.hidden.py",
        "src/../../x.py",
        "src/a.exe",
        "src\\a.py",
        "src/.git/config",
        "src/a.py:evil",
    ],
)
def test_reject_unsafe_paths(path):
    with pytest.raises(WorkspaceError):
        safe_path(path)


def test_snapshot_skips_secrets_symlinks(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("x = 1")
    (source / ".env").write_text("SECRET=abc")
    (source / "linked.py").symlink_to(source / "main.py")
    target = tmp_path / "target"
    target.mkdir()
    result = snapshot(source, target)
    assert result == {"main.py": b"x = 1"}
    assert not (target / ".env").exists()
    assert not (target / "linked.py").exists()


from contextlib import contextmanager


@contextmanager
def fake_gemini(response):
    module = types.ModuleType("cmf_dev_studio.llm.gemini")

    class GeminiClient:
        def generate(self, prompt):
            if "ROLE: ANALYST" in prompt:
                return json.dumps(
                    {
                        "requirements": ["Implement requested change"],
                        "acceptance": ["Requested behavior works"],
                    }
                )
            if "ROLE: TESTER" in prompt:
                return json.dumps({"issues": []})
            return response

    module.GeminiClient = GeminiClient
    with patch.dict(sys.modules, {"cmf_dev_studio.llm.gemini": module}):
        yield


def test_new_project_proposal_api(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    project = client.post(
        "/api/projects", json={"location": str(tmp_path), "name": "hello-fastapi"}
    ).json()
    response = {
        "operations": [
            {
                "action": "create",
                "path": "main.py",
                "content": "from fastapi import FastAPI\napp = FastAPI()\n",
            },
            {
                "action": "create",
                "path": "tests/test_main.py",
                "content": "def test_ok(): assert True\n",
            },
        ]
    }
    with fake_gemini(json.dumps(response)):
        submitted = client.post(
            f"/api/projects/{project['id']}/proposals",
            json={"task": "Create a FastAPI app"},
        )
        assert submitted.status_code == 202, submitted.text
        proposal_id = submitted.json()["id"]
        for _ in range(100):
            proposal = client.get(f"/api/proposals/{proposal_id}").json()
            if proposal["status"] in ("ready", "failed"):
                break
            time.sleep(0.02)
    assert proposal["status"] == "ready", proposal
    assert len(proposal["changes"]) == 2
    assert "+from fastapi import FastAPI" in proposal["changes"][0]["diff"]
    assert list(Path(project["path"]).iterdir()) == []


def test_existing_project_proposal_preserves_original(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("answer = 1\n")
    project = client.post("/api/projects/register", json={"path": str(source)}).json()
    preview = client.post(
        f"/api/projects/{project['id']}/context/preview", json={"paths": ["main.py"]}
    ).json()
    result = {
        "operations": [
            {"action": "modify", "path": "main.py", "content": "answer = 2\n"}
        ]
    }
    with fake_gemini(json.dumps(result)):
        submitted = client.post(
            f"/api/projects/{project['id']}/proposals",
            json={
                "task": "Update answer",
                "context_paths": ["main.py"],
                "context_digest": preview["digest"],
            },
        )
        assert submitted.status_code == 202, submitted.text
        for _ in range(100):
            proposal = client.get("/api/proposals/" + submitted.json()["id"]).json()
            if proposal["status"] in ("ready", "failed"):
                break
            time.sleep(0.02)
    assert proposal["status"] == "ready", proposal
    assert "-answer = 1" in proposal["changes"][0]["diff"]
    assert "+answer = 2" in proposal["changes"][0]["diff"]
    assert (source / "main.py").read_text() == "answer = 1\n"


def test_proposal_diff_preview_is_read_only_and_detects_conflicts(tmp_path):
    client = TestClient(create_app(tmp_path / "data"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("answer = 1\n")
    project = client.post("/api/projects/register", json={"path": str(source)}).json()
    context = client.post(
        f"/api/projects/{project['id']}/context/preview", json={"paths": ["main.py"]}
    ).json()
    with fake_gemini(
        json.dumps(
            {
                "operations": [
                    {"action": "modify", "path": "main.py", "content": "answer = 2\n"}
                ]
            }
        )
    ):
        created = client.post(
            f"/api/projects/{project['id']}/proposals",
            json={
                "task": "Update answer",
                "context_paths": ["main.py"],
                "context_digest": context["digest"],
            },
        ).json()
        for _ in range(100):
            proposal = client.get(f"/api/proposals/{created['id']}").json()
            if proposal["status"] in ("ready", "failed"):
                break
            time.sleep(0.02)
    assert proposal["status"] == "ready"
    result = client.get(
        f"/api/proposals/{created['id']}/preview", params={"path": "main.py"}
    )
    assert result.status_code == 200, result.text
    assert result.json()["before"] == "answer = 1\n"
    assert result.json()["after"] == "answer = 2\n"
    assert (source / "main.py").read_text() == "answer = 1\n"
    assert (
        client.get(
            f"/api/proposals/{created['id']}/preview", params={"path": "../secret.py"}
        ).status_code
        == 409
    )
    (source / "main.py").write_text("answer = 99\n")
    assert (
        client.get(
            f"/api/proposals/{created['id']}/preview", params={"path": "main.py"}
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "language, label, filename",
    [
        ("python", "Python", "app.py"),
        ("java", "Java", "App.java"),
        ("kotlin", "Kotlin", "App.kt"),
    ],
)
def test_empty_project_language_reaches_all_agents(tmp_path, language, label, filename):
    """An empty project supplies its configured language to analyst, developer and tester."""
    from unittest.mock import Mock

    from cmf_dev_studio.projects import ProjectLanguage, ProjectManager
    from cmf_dev_studio.workspaces import WorkspaceService

    manager = ProjectManager(tmp_path / "studio")
    project = manager.create(
        "Calculator", language=ProjectLanguage(language), location=tmp_path
    )
    service = WorkspaceService(manager)
    llm = Mock()
    llm.generate.side_effect = [
        json.dumps({"requirements": ["Calculator"], "acceptance": ["Works"]}),
        json.dumps(
            {"operations": [{"action": "create", "path": filename, "content": ""}]}
        ),
        json.dumps({"issues": []}),
    ]
    module = types.ModuleType("cmf_dev_studio.llm.gemini")
    module.GeminiClient = lambda: llm
    with patch.dict(sys.modules, {"cmf_dev_studio.llm.gemini": module}):
        submitted = service.submit(project.id, "Create a calculator", [])
        for _ in range(100):
            proposal = service.get(submitted["id"])
            if proposal["status"] in ("ready", "failed"):
                break
            time.sleep(0.02)
    assert proposal["status"] == "ready", proposal
    assert len(llm.generate.call_args_list) == 3
    for call in llm.generate.call_args_list:
        assert f"Primary implementation language is {label}" in call.args[0]
    assert proposal["task"] == "Create a calculator"


def test_empty_patch_is_not_a_context_permission_error():
    """An empty model response must not be presented as missing authorization."""
    from cmf_dev_studio.workspaces import validate_operations

    with pytest.raises(WorkspaceError, match="Expected 1-12 file operations") as error:
        validate_operations([], {}, set())
    assert "context approval" not in str(error.value)


@pytest.mark.parametrize("existing", [False, True])
def test_create_without_context(existing):
    """New files require no approval, even in a populated repository."""
    from cmf_dev_studio.workspaces import validate_operations

    original = {"old.py": b"x = 1"} if existing else {}
    validate_operations(
        [{"action": "create", "path": "new.py", "content": "x = 2"}], original, set()
    )


def test_empty_project_retries_empty_patch_without_context(tmp_path):
    """A failed first generation can recover without requesting nonexistent files."""
    from unittest.mock import Mock

    from cmf_dev_studio.projects import ProjectLanguage, ProjectManager
    from cmf_dev_studio.workspaces import WorkspaceService

    manager = ProjectManager(tmp_path / "studio")
    project = manager.create(
        "Calculator", language=ProjectLanguage.JAVA, location=tmp_path
    )
    service = WorkspaceService(manager)
    llm = Mock()
    llm.generate.side_effect = [
        json.dumps({"requirements": ["Calculator"], "acceptance": ["Works"]}),
        json.dumps({"operations": []}),
        json.dumps(
            {
                "operations": [
                    {"action": "create", "path": "App.java", "content": "class App {}"}
                ]
            }
        ),
        json.dumps({"issues": []}),
    ]
    module = types.ModuleType("cmf_dev_studio.llm.gemini")
    module.GeminiClient = lambda: llm
    with patch.dict(sys.modules, {"cmf_dev_studio.llm.gemini": module}):
        submitted = service.submit(project.id, "Create calculator", [])
        for _ in range(100):
            proposal = service.get(submitted["id"])
            if proposal["status"] in ("ready", "failed"):
                break
            time.sleep(0.02)
    assert proposal["status"] == "ready", proposal
    assert "EMPTY PROJECT" in llm.generate.call_args_list[1].args[0]
    assert "Expected 1-12 file operations" in llm.generate.call_args_list[2].args[0]
    assert proposal["approved_paths"] == []
    assert not list(project.path.iterdir())
