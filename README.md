# Multi-Agent Studio

Local repository IDE with Monaco, terminal, explicit AI context approval and isolated test execution.

## Architecture

`orchestrator.py` is the only orchestration module. `Orchestrator.prepare` coordinates Analyst, Developer and Tester; `reviewed_patch` coordinates bounded patch reviews; `repository_test_cycle` schedules test runs and repairs. The agents own their prompts and structured response contracts (`contracts.py`). `workspaces.py` owns snapshots, permissions, persistence, test/apply locking and filesystem operations. `project_runners.py` selects and executes the appropriate Docker runner. The API exposes repository proposals; the chat is the sole development interface. Generation and testing are separate phases of the same persisted proposal, so the user can retry a failed test without regenerating the task.

The standalone single-file mission API, CLI and UI have been retired, not wrapped. Existing SQLite mission tables are left untouched; historical standalone runs are no longer displayed. The CLI entry point now starts the local API. The proposal history and project registry are preserved.

## Setup and validation

Configure Gemini in `.env` as before. Run `uv sync`, then `uv run pytest -q -m "not integration"`. In `frontend`, run `npm install` and `npm run build`.

Build runner images from the root:

```sh
docker build -f docker/project-test-runner.Dockerfile -t multi-agent-studio-project-tests:2.2 .
docker build -f docker/maven-test-runner.Dockerfile -t multi-agent-studio-maven-tests:4 .
docker build -f docker/gradle-test-runner.Dockerfile -t multi-agent-studio-gradle-tests:4 .
uv run pytest -q -m integration
```

JVM images preload dependencies of `examples/java-maven` and `examples/kotlin-gradle`; arbitrary dependencies are not supported automatically. Runtime containers have no network. Real JVM execution requires Docker validation on the target machine.

Start backend from root:

```sh
uv run uvicorn multi_agent_software_team.api.app:app --reload --reload-dir src --host 127.0.0.1 --port 8000
```

Start frontend from `frontend`: `npm run dev`. Open http://127.0.0.1:5173.

## Safety

Approve exact file contents before sending to Gemini. Changes are generated in isolated snapshots, reviewed and tested before explicit application. Existing projects require additional write authorization. The original repository is not mounted in test containers. Unsupported runners and infrastructure errors do not count as passing tests. Only known dependencies are available offline. This is a local development tool, not a security boundary for hostile repositories.
