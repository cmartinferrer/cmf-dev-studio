"""V4 regression contracts: no language-specific agent restrictions or split engines."""

import json
from unittest.mock import Mock

import pytest

from cmf_dev_studio.orchestrator import Orchestrator
from cmf_dev_studio.project_runners import UnsupportedRunner, select_runner
from cmf_dev_studio.workspaces import WorkspaceError, validate_operations


def test_orchestrator_roles_and_permission_validation():
    responses = [
        json.dumps(
            {
                "requirements": ["GET /version returns 0.1.0"],
                "acceptance": ["GET /version returns a literal version string"],
            }
        ),
        json.dumps(
            {
                "operations": [
                    {
                        "action": "modify",
                        "path": "src/Main.java",
                        "content": "class Main {}",
                    }
                ]
            }
        ),
        json.dumps({"issues": []}),
    ]
    llm = Mock()
    llm.generate.side_effect = responses
    engine = Orchestrator(llm)
    plan = engine.plan_patch(
        "Add version endpoint",
        "src/Main.java",
        "FILE: src/Main.java\nclass Main {}",
        ["Java"],
    )
    original = {"src/Main.java": b"class Main {}"}
    operations = engine.generate_patch(
        "Return JSON operations",
        plan,
        validate=lambda ops: validate_operations(ops, original, {"src/Main.java"}),
    )
    assert not engine.review_patch("Add version endpoint", plan, operations)
    assert llm.generate.call_count == 3
    assert "ROLE: ANALYST" in llm.generate.call_args_list[0].args[0]
    assert "ROLE: DEVELOPER" in llm.generate.call_args_list[1].args[0]
    assert "ROLE: TESTER" in llm.generate.call_args_list[2].args[0]
    with pytest.raises(WorkspaceError, match="Permission required"):
        validate_operations(operations, original, set())


@pytest.mark.parametrize(
    "manifest,expected",
    [
        ("pom.xml", "maven"),
        ("build.gradle.kts", "gradle"),
        ("build.gradle", "gradle"),
        ("app.py", "pytest"),
    ],
)
def test_runner_selection_by_build_manifest(tmp_path, manifest, expected):
    (tmp_path / manifest).write_text("sample")
    if expected in ("maven", "gradle"):
        (tmp_path / "src/test/java").mkdir(parents=True)
        (tmp_path / "src/test/java/AppTest.java").write_text("class AppTest {}")
    assert select_runner(tmp_path).name == expected


def test_runner_rejects_unsupported_project(tmp_path):
    (tmp_path / "README.md").write_text("sample")
    with pytest.raises(UnsupportedRunner):
        select_runner(tmp_path)


@pytest.mark.parametrize(
    "manifest,source_path",
    [
        ("pom.xml", "src/main/java/demo/App.java"),
        ("build.gradle.kts", "src/main/kotlin/demo/App.kt"),
    ],
)
def test_end_to_end_project_patch_review_test_apply_with_mocked_container(
    tmp_path, monkeypatch, manifest, source_path
):
    """API -> roles -> safe snapshot -> selected runner -> explicit apply."""
    import sys
    import time
    import types
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from cmf_dev_studio import workspaces
    from cmf_dev_studio.api.app import create_app

    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / manifest).write_text("build configuration")
    file = project_root / source_path
    file.parent.mkdir(parents=True)
    file.write_text("original source")
    test_source = project_root / (
        "src/test/java/demo/AppTest.java"
        if manifest == "pom.xml"
        else "src/test/kotlin/demo/AppTest.kt"
    )
    test_source.parent.mkdir(parents=True)
    test_source.write_text("independent tests")
    client = TestClient(create_app(tmp_path / "data"))
    project = client.post(
        "/api/projects/register", json={"path": str(project_root)}
    ).json()
    preview = client.post(
        f"/api/projects/{project['id']}/context/preview", json={"paths": [source_path]}
    ).json()
    assert "digest" in preview, preview

    responses = [
        json.dumps(
            {
                "requirements": ["Expose a version"],
                "acceptance": ["Returns version 0.1.0"],
            }
        ),
        json.dumps(
            {
                "operations": [
                    {
                        "action": "modify",
                        "path": source_path,
                        "content": "revised source",
                    }
                ]
            }
        ),
        json.dumps({"issues": []}),
    ]
    module = types.ModuleType("cmf_dev_studio.llm.gemini")

    class FakeGemini:
        def generate(self, prompt):
            return responses.pop(0)

    module.GeminiClient = FakeGemini
    with patch.dict(sys.modules, {"cmf_dev_studio.llm.gemini": module}):
        submitted = client.post(
            f"/api/projects/{project['id']}/proposals",
            json={
                "task": "Add version",
                "context_paths": [source_path],
                "context_digest": preview["digest"],
            },
        )
        assert submitted.status_code == 202, submitted.text
        proposal_id = submitted.json()["id"]
        for _ in range(100):
            result = client.get(f"/api/proposals/{proposal_id}").json()
            if result["status"] in ("ready", "failed"):
                break
            time.sleep(0.02)
    assert result["status"] == "ready", result
    assert result["plan"]["acceptance"] == ["Returns version 0.1.0"]
    assert file.read_text() == "original source"
    chosen = []

    def fake_runner(workspace, spec):
        chosen.append(spec.name)
        return True, "Runner: " + spec.name + " (exit 0)\n1 test passed"

    monkeypatch.setattr(workspaces, "execute_runner", fake_runner)
    assert (
        client.post(
            f"/api/proposals/{proposal_id}/test", json={"approval": "invalid"}
        ).status_code
        == 409
    )
    assert not chosen
    preview = client.get(f"/api/proposals/{proposal_id}/test").json()
    assert not chosen
    tested = client.post(
        f"/api/proposals/{proposal_id}/test", json={"approval": preview["approval"]}
    )
    assert tested.status_code == 200, tested.text
    assert tested.json()["status"] == "tested"
    assert chosen == ["maven" if manifest == "pom.xml" else "gradle"]
    assert file.read_text() == "original source"
    for body, status in [
        ({}, 422),
        ({"approved": False}, 409),
        ({"approved": "true"}, 422),
    ]:
        assert (
            client.post(f"/api/proposals/{proposal_id}/apply", json=body).status_code
            == status
        )
        assert file.read_text() == "original source"
    applied = client.post(
        f"/api/proposals/{proposal_id}/apply",
        json={"approved": True},
    )
    assert applied.status_code == 200, applied.text
    assert file.read_text() == "revised source"


def test_local_runner_uses_disposable_copy(tmp_path):
    import sys

    from cmf_dev_studio.project_runners import RunnerSpec, execute_runner

    (tmp_path / "source.txt").write_text("original")
    command = (
        sys.executable,
        "-c",
        "from pathlib import Path; Path('source.txt').write_text('changed'); print('ok')",
    )
    passed, output = execute_runner(tmp_path, RunnerSpec("python", command))
    assert passed and "ok" in output
    assert (tmp_path / "source.txt").read_text() == "original"


def test_tampered_workspace_cannot_be_applied(tmp_path, monkeypatch):
    from cmf_dev_studio.projects.manager import ProjectManager
    from cmf_dev_studio.workspaces import WorkspaceService, tree_digest

    manager = ProjectManager(tmp_path / "data")
    project = manager.create("example", location=tmp_path)
    service = WorkspaceService(manager)
    proposal_id = "c" * 32
    workspace = service.root / proposal_id
    workspace.mkdir()
    (workspace / "main.py").write_text("original generated content")
    with service._db() as db:
        db.execute(
            "INSERT INTO workspace_proposals(id,project_id,status,task,created_at,changes,tested_digest) VALUES (?,?,?,?,?,?,?)",
            (
                proposal_id,
                project.id,
                "tested",
                "task",
                "now",
                json.dumps(
                    [
                        {
                            "action": "create",
                            "path": "main.py",
                            "before_sha256": None,
                            "size": 26,
                            "diff": "",
                        }
                    ]
                ),
                tree_digest(workspace),
            ),
        )
    (workspace / "main.py").write_text("tampered after test")
    with pytest.raises(WorkspaceError, match="changed after testing"):
        service.apply(proposal_id, True)
    assert not (project.path / "main.py").exists()
