# Multi-Agent Software Team

An educational multi-agent system built with Python to explore how specialized AI agents collaborate through a central orchestrator to solve software development tasks.

The project is developed incrementally, focusing on multi-agent orchestration, shared state, LLM integration, automated testing, error handling, and isolated code execution without relying on high-level agent frameworks.

## Current Features

- **Mission management:** Shared mission state using Python dataclasses, including per-attempt execution history.
- **Analyst Agent:** Generates software requirements dynamically using Google Gemini.
- **Developer Agent:** Generates Python implementations and revises failed implementations using pytest feedback.
- **Tester Agent:** Generates pytest tests based on the requirements and generated implementation.
- **Orchestrator:** Coordinates agents, supports optional test execution, retries failed implementations, and records each runner outcome.
- **LLM abstraction:** Uses an `LLMClient` protocol to decouple agents from specific providers.
- **Gemini integration:** Uses the official Google GenAI SDK.
- **Test runner abstraction:** Uses a `TestRunner` protocol to decouple orchestration from the execution environment.
- **Docker Test Runner:** Independently executes Python code and pytest tests inside a restricted Docker container.
- **Execution results:** Distinguishes successful tests, test failures, and Docker infrastructure errors.
- **CLI entry point:** Accepts user missions, runs the complete agent pipeline, and executes generated code and tests in Docker by default.
- **Automated testing:** Includes mocked unit tests and integration tests using real Docker containers with predefined, trusted code.

> **Security:** Docker execution is enabled by default for a complete end-to-end workflow. The restrictions reduce exposure but do not guarantee protection from malicious code. Use `--generate-only` to disable execution.

## Architecture

```text
                         User
                          |
                          v
                     Orchestrator
                          |
                          v
                    Analyst Agent
                          |
                          v
                   Developer Agent
                          |
                          v
                    Tester Agent
                          |
                          v
                 Optional TestRunner
                    /           \
             Not configured   Configured
                  |               |
                  |          TestResult
                  |               |
                  +-------+-------+
                          |
                          v
                    Mission Result

     Analyst, Developer, Tester -> LLMClient
                                      |
                                      v
                                 GeminiClient
                                      |
                                      v
                                 Google Gemini

     DockerTestRunner implements TestRunner (independently tested)
                          |
                          v
                  Docker Container
                          |
                          v
                        pytest
```

The orchestrator coordinates three specialized agents: `AnalystAgent` generates requirements, `DeveloperAgent` produces an implementation, and `TesterAgent` generates pytest tests. They share a single `Mission` object containing the mission description, requirements, code, tests, feedback, attempt count, and status.

The agents use the `LLMClient` abstraction to communicate with Gemini. An optional `TestRunner` can validate the generated code after all agents finish. On test failures, the developer may regenerate the implementation using feedback while the original tests remain unchanged. **The CLI connects the runner by default**; `--generate-only` disables execution.

## Requirements

- Python (version specified in `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Google Gemini API key for the CLI example
- Docker with a running daemon for Docker integration tests or standalone Docker runner execution

## Getting Started

Install project dependencies:

```bash
uv sync
```

Create a `.env` file in the project root:

```dotenv
GOOGLE_API_KEY=your_google_api_key
```

The application loads environment variables using `python-dotenv`.

> **Security:** Never commit `.env` or API credentials. Ensure `.env` is included in `.gitignore`.

Run the example mission:

```bash
uv run python main.py
```

The orchestrator runs `AnalystAgent`, `DeveloperAgent`, and `TesterAgent` sequentially. The resulting mission contains requirements, generated code, tests, and execution status. The CLI executes generated tests in Docker by default and displays their results.

## LLM Integration

The `LLMClient` protocol defines a provider-independent interface:

```python
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...
```

`GeminiClient` adapts the official Google GenAI SDK to this interface. Dependency injection keeps agent logic independent of the provider and makes deterministic unit testing with mocks possible.

## Mission Lifecycle and Error Handling

| Status | Description |
|---|---|
| `PENDING` | The mission has not started. |
| `IN_PROGRESS` | The workflow is running. |
| `COMPLETED` | All agents finished successfully and, if a runner was configured, its tests passed. |
| `FAILED` | An agent or runner raised an exception, or the configured runner reported a failed execution. |

If an agent or runner raises an exception, the orchestrator stops the workflow, sets the status to `FAILED`, stores the exception message in `mission.feedback`, and returns the updated mission. Previously generated information remains available.

> **Important:** Without a configured runner, `COMPLETED` means that all agents finished successfully; it does **not** mean that the generated implementation passed tests.

### Optional Test Runner Integration

The orchestrator accepts a `TestRunner` through dependency injection:

```python
orchestrator = Orchestrator(llm=llm, runner=runner)
```

When a runner is supplied, the orchestrator:

1. Executes the analyst, developer, and tester agents.
2. Increments `mission.attempts` when invoking the runner.
3. Calls `runner.run(code=mission.code, tests=mission.tests)`.
4. Stores the execution output or error details in `mission.feedback`.
5. Marks the mission `COMPLETED` only when the runner reports a successful `PASSED` result; otherwise, marks it `FAILED`.

When no runner is supplied (`Orchestrator(llm=llm)`), the previous workflow is preserved. There are no automatic retries or developer feedback loops yet.

**Safety:** The optional runner integration is verified using mocked responses. Do not inject `DockerTestRunner` into a workflow that passes it untrusted LLM-generated code until an appropriate security review and containment solution are in place.

## Developer Feedback and Retry Policy

When a `TestRunner` is injected, the orchestrator can retry implementations that fail pytest assertions:

1. `AnalystAgent` generates requirements once.
2. `DeveloperAgent` generates the initial implementation.
3. `TesterAgent` generates tests once.
4. The runner evaluates the current implementation against those tests.
5. On `TEST_FAILED`, the orchestrator stores the failure output in `mission.feedback`, and, if attempts remain, asks `DeveloperAgent` to revise the previous implementation using that feedback.
6. On `PASSED`, the mission becomes `COMPLETED`. On exhausted attempts or `INFRASTRUCTURE_ERROR`, it becomes `FAILED`.

`max_attempts` defaults to `3` and includes the initial test execution (up to two corrections). `mission.attempts` counts runner invocations and is reset at the start of each run. An orchestrator without a runner retains the original generation-only behavior.

```python
orchestrator = Orchestrator(llm=llm, runner=trusted_runner, max_attempts=3)
```

**Security:** This example requires a runner appropriate for the trust level of the input. The CLI still does not configure a runner; the Docker implementation has not been approved for untrusted LLM-generated code. Unit tests exercise retry behavior with mocked runners only.

## Execution History

Each `Mission` maintains a `history` list of immutable `ExecutionAttempt` snapshots. Every completed runner invocation records the attempt number, exact code submitted, `TestStatus`, exit code, standard output, and standard error. Previous entries are preserved when the developer produces a correction.

`mission.attempts` still counts runner invocations; `mission.feedback` holds the latest feedback. If a runner raises an exception before returning a `TestResult`, the invocation is counted but no synthetic history entry is added. When a mission is run again, its history is reset alongside its attempt counter.

History is held in memory; it is not persisted to disk and is not generated when no runner is configured. Unit tests use mocked runners, and the CLI still does not execute LLM-generated code.

## Docker Test Runner

The standalone `DockerTestRunner` creates a temporary workspace, writes the implementation to `solution.py` and tests to `test_solution.py`, launches a restricted container, executes pytest, captures results, attempts to remove the container, verifies its absence, and removes the workspace.

### Execution Results

`DockerTestRunner.run(code, tests)` returns a `TestResult` with `success`, `status`, `exit_code`, `stdout`, and `stderr`.

| Status | Description |
|---|---|
| `TestStatus.PASSED` | pytest exited successfully. |
| `TestStatus.TEST_FAILED` | pytest exited unsuccessfully without a recognized Docker infrastructure error. |
| `TestStatus.INFRASTRUCTURE_ERROR` | Recognized Docker invocation/daemon error, timeout, or unconfirmed container cleanup. |

Infrastructure errors are classified using known exit codes and messages; some errors can be ambiguous.

### Docker Isolation

The runner applies the following restrictions:

- Non-root user (`10001:10001`)
- Disabled network access (`--network=none`) and IPC isolation (`--ipc=none`)
- Read-only root filesystem and read-only workspace mount
- Dropped Linux capabilities and disabled privilege escalation
- CPU, memory, process, and file descriptor limits
- Restricted temporary filesystem
- Disabled Python bytecode writes and automatic pytest plugin loading

Build the dedicated runner image:

```bash
docker build -f docker/test-runner.Dockerfile -t multi-agent-test-runner:latest .
```

### Temporary Workspaces

Each execution creates a temporary directory under `.runner-workspaces/` containing only `solution.py` and `test_solution.py`:

```text
.runner-workspaces/
└── multi-agent-tests-<unique-id>/
    ├── solution.py
    └── test_solution.py
```

Only this temporary directory is bind-mounted into the container, not the entire project. This avoids exposing `.env`, `.git`, and other project files through the workspace mount. The temporary directory is removed after normal execution.

Ensure `.gitignore` includes:

```gitignore
.env
.runner-workspaces/
```

### Security Limitations

**The Docker runner is not approved for running untrusted LLM-generated code.** Docker restrictions reduce exposure but do not prove isolation against hostile code. Docker daemon security, container escapes, host filesystem access, timeouts, cleanup failures, and resource exhaustion require further review. Real integration tests use only predefined, trusted Python code.

## Development and Testing

The project uses pytest. Agent and orchestrator tests mock external dependencies to avoid Gemini API calls and keep results reproducible.

### Unit Tests

Run unit tests without Docker:

```bash
uv run pytest -v -m "not integration"
```

The optional runner integration is covered by mocked unit tests for success, test failure, infrastructure failure, exceptions, and compatibility with the no-runner workflow.

### Docker Integration Tests

Start Docker and build the runner image:

```bash
docker build -f docker/test-runner.Dockerfile -t multi-agent-test-runner:latest .
```

Then run:

```bash
uv run pytest -v -m integration
```

The integration tests verify execution of trusted Python code, classification of passing and failing tests, captured output, and container cleanup.

### Complete Test Suite

```bash
uv run pytest -v
```

The full test suite includes unit tests and Docker integration tests. Run `uv run pytest -v` locally to verify both.

## Project Status

**Early development — educational prototype.**

Implemented: shared mission state, sequential multi-agent orchestration, Gemini integration, provider abstraction, mission lifecycle and error handling, standalone Docker test execution, result classification, optional runner dependency injection, and unit/integration testing.

### Planned Improvements

- Review and strengthen the security of isolated execution before using LLM-generated code.
- Add feedback loops between `DeveloperAgent` and test execution.
- Introduce configurable retry policies.
- Improve logging and execution observability.
- Explore more advanced orchestration strategies.

## License

Not yet specified.

## Complete end-to-end CLI (default)

The CLI runs the entire workflow: user task -> Gemini -> Analyst -> Developer
-> Tester -> Docker/pytest -> feedback -> Developer retries -> final result.

```bash
# Build the test image once (Docker must be running).
docker build -t multi-agent-test-runner:latest -f docker/test-runner.Dockerfile .

# Full workflow with a custom task:
uv run python main.py "Implement a Python function add(a, b) returning their sum"

# Equivalent installed command:
uv run multi-agent-software-team "Implement a Python function add(a, b) returning their sum"

# Generate code without running it:
uv run python main.py --generate-only "Implement add(a, b)"

# Run the complete integration with a deterministic fake LLM and real Docker:
uv run pytest -v tests/integration/test_full_workflow_integration.py

# Run all tests:
uv run pytest -v
```

Docker restrictions include a non-root container, no network, a read-only
filesystem and workspace, dropped Linux capabilities, resource limits, and a
process timeout. The Docker socket and home directory are not mounted.
**This is risk reduction, not a guarantee against malicious generated code.**
Do not grant the container elevated privileges or mount sensitive files.


## Live execution timeline (Rich)

The CLI now renders agent progress, Docker test outcomes, retries, and a readable
mission summary in real time using Rich. By default it displays the final code
and requirements without flooding the screen with pytest tracebacks.

```bash
uv sync
uv run python main.py "Implement a Python function add(a, b) returning their sum"
uv run python main.py --verbose "Implement a Python function add(a, b) returning their sum"
uv run python main.py --generate-only --example
```

`--verbose` also shows generated pytest tests and complete output for every
Docker attempt. The execution core emits typed `ExecutionEvent` notifications
through an optional `on_event` callback. Rich is only a terminal adapter;
future web/GUI/API clients can subscribe to the same events without changing
the agents, runner, or orchestration logic. The existing `Mission.history`
continues to store full attempt data.

The sandbox reduces risk but cannot guarantee secure execution of malicious
code; use a suitably isolated Docker host for untrusted generation.

### Understanding test failures and developer corrections

The Rich CLI displays failed pytest test names and their error messages in a
readable panel. It preserves the complete error text instead of truncating it
into a single line. After a retry, the mission summary reports how many lines
were added and removed between the code versions submitted to Docker.

Use `--verbose` to inspect the complete unified code diff (with additions and
removals), generated pytest tests, and the full pytest output for each attempt:

```bash
uv run python main.py "Implement a Python function add(a, b) returning their sum" --verbose
```

These diagnostics are derived from the existing `Mission.history` records and
do not change agent decisions, retry behavior, or Docker execution. A passing
test suite does not independently guarantee correctness of generated code.
## Multi-Agent Studio — Project Registry (first iteration)

The UI-independent `ProjectManager` is the first building block for the future
React/FastAPI Studio. It persists project metadata in SQLite and supports both:

- **Managed projects:** `create(name, description)` creates a new empty workspace
  under the Studio data directory.
- **Existing projects:** `register_existing(path, name, description)` registers
  a directory without modifying its files. These projects are marked read-only
  in this first iteration.

Other operations: `get(project_id)` and `list_projects()`.

Try the manager locally, without Gemini or Docker:

```python
from multi_agent_software_team.projects import ProjectManager

manager = ProjectManager('.studio-data')
new_project = manager.create('Calculator')
existing_project = manager.register_existing('/absolute/path/to/your/repository')
for project in manager.list_projects():
    print(project.name, project.kind.value, project.path)
```

`.studio-data/` is ignored by Git. The registry **does not** run agents, import
existing source files, copy repositories, or modify existing projects. It is
not yet a history-of-missions service, API, or web frontend; those will be
implemented in subsequent iterations. Existing projects must remain available
at their registered paths. Back up the Studio data directory to preserve the
SQLite registry and managed workspaces.

Run focused tests:

```bash
uv run pytest -v tests/test_project_manager.py
```

## Multi-Agent Studio: local REST API (iteration 2)

The project registry is now available through a **local FastAPI backend**. It does
not invoke Gemini, execute generated code, or change existing repositories.

Install the new Python dependencies and update `uv.lock` on your machine:

```bash
uv sync
```

Start the API **bound to localhost only** (do not use `--host 0.0.0.0`):

```bash
uv run uvicorn multi_agent_software_team.api.app:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/docs> for interactive Swagger documentation.
Data is stored in `.studio-data/` by default; set `STUDIO_DATA_DIR` to override.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create an empty managed workspace |
| POST | `/api/projects/register` | Register an existing local directory (read-only) |
| GET | `/api/projects/{project_id}` | Retrieve project metadata |

Example JSON for creating a project: `{"name": "Calculator", "description": "Demo"}`.
To register a directory: `{"path": "/absolute/path/to/repository"}`.

**Security scope:** This API has no authentication and exposes local filesystem
paths. Keep it on `127.0.0.1` and do not expose it to your network or the
Internet. Registration does not authorize agent modifications. A later iteration
will add explicit workspace access controls, safe change review, and execution.

Run the tests with `uv run pytest -v` (Docker integration tests require Docker).
The current ZIP retains the previous `uv.lock`; `uv sync` regenerates it with
FastAPI, Uvicorn and HTTPX on the developer machine.


## Multi-Agent Studio web UI (React + TypeScript)

This is the first **project dashboard** UI, not yet an agent execution IDE. It uses the existing REST endpoints to list, create, and register projects, and displays project metadata. Existing folders are registered read-only; this release does not browse, edit, or execute their code.

Run in two terminals from the repository root:

```bash
uv sync
uv run uvicorn multi_agent_software_team.api.app:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` to the FastAPI server on `127.0.0.1:8000`; no CORS configuration or public exposure is needed. Use `npm run build` to verify TypeScript and the production bundle. Commit the generated `frontend/package-lock.json` for reproducible installs.

**Opening an existing project:** enter an absolute folder path on the machine running FastAPI. Browsers cannot give the server unrestricted local folder access; a folder picker and safe workspace copy/edit workflow will come later.

**Security:** Both servers are for trusted local development only. The API currently has no authentication; do not expose it to your network or the Internet.

## Studio missions API (backend iteration)

The Studio API now supports asynchronous, persistent mission runs. Run FastAPI locally:

```bash
uv run uvicorn multi_agent_software_team.api.app:app --reload --host 127.0.0.1 --port 8000
```

- `POST /api/projects/{project_id}/missions` with `{"description":"Create a Python function..."}` returns `202` and a run ID.
- `GET /api/projects/{project_id}/missions` lists saved runs.
- `GET /api/missions/{run_id}` retrieves status and generated code/tests/attempts when finished.
- `GET /api/missions/{run_id}/events?after_id=0` retrieves ordered progress events; poll with the last received event ID.

Only one queued/running mission is allowed per project. Runs use Gemini and the Docker test runner, and require the same credentials and local Docker image as the CLI. **Generated files are stored in SQLite, not written to registered project folders.** Existing repositories remain untouched. This is a local-only, unauthenticated API: do not expose it to a network. Process restarts do not resume in-flight missions; recovery, cancellation, streaming and applying changes are future iterations.

## Workspace UX v2

- The **Open existing project** dialog has a **Browse…** button. It lists folders on the FastAPI host (not on a remote browser client). By default it is restricted to the server user's home directory. Set `STUDIO_BROWSE_ROOT=/absolute/allowed/directory` before starting Uvicorn to restrict it further. Hidden directories and symlinks are excluded.
- Each project workspace now has **Files**, **Agent missions**, and **Project details** tabs.
- **Files** includes a bounded filename search, line numbers, and lightweight syntax highlighting for Python and JavaScript/TypeScript. Preview remains read-only.
- Filename search inspects up to 5,000 entries and returns up to 100 results; it ignores hidden files, symlinks and dependency/build folders. No file content is sent by search.

For local validation: `uv run pytest -q -m 'not integration'`, then `cd frontend && npm install && npm run build`. Run FastAPI and `npm run dev` to verify the folder picker, tabs, search, and preview. Do not commit until functional checks pass.

## Repository Intelligence v1 (read-only)

The **Repository Insights** tab inventories source file names, language extensions,
and recognized manifests without sending repository contents to Gemini. Select up to
8 source files, click **Review selected content**, inspect the full preview, then
**Approve & go to missions**. The approved file paths and a SHA-256 fingerprint
are submitted with the next mission. The API rereads and checks the files against
the approved fingerprint before starting, and includes the selected contents as
reference code for Analyst, Developer and Tester. The source files are never
modified. If any file changes, review and approve the selection again.

Endpoints:

- `GET /api/projects/{project_id}/insights`
- `POST /api/projects/{project_id}/context/preview` with `{"paths": ["src/main.py"]}`
- `POST /api/projects/{project_id}/missions` accepts optional `context_paths`
  and `context_digest` from the preview. Missions without context work as before.

**Safety and limitations:** inventory is bounded to 3,000 visited entries and
160 candidate files. Context is limited to 8 files, 12 KiB each, 32 KiB total;
only selected source-code extensions are accepted. Hidden paths, symlinks,
known generated directories, suspicious names and common credential patterns are
excluded. These are *best-effort* protections, not a guarantee that a source file
contains no private information. Always review the exact preview before approval.
Do not approve confidential or proprietary code for an external model unless you
have permission to share it. Context is passed in-memory to the execution worker,
not stored verbatim in the mission description; however, generated model output
and mission events may include portions of it. The Gemini provider processes
approved content externally. The implementation still generates standalone code
and tests; it does not edit or apply patches to registered projects.

## v2.1 — Workspace proposals (experimental)

This release adds the **Workspace proposals** tab for both managed (new) and registered existing Python projects. It snapshots a bounded set of safe text files into `.studio-data/proposal-workspaces/<proposal-id>/`, then requests a structured file proposal from Gemini. The UI shows unified diffs for each proposed create/modify/delete operation. **The original project is never changed by this workflow.** Project-level pytest execution and applying reviewed changes are not implemented in v2.1.

**Test A — new project:** Create a managed project named `hello-fastapi`, open **Workspace proposals**, and request: `Create a FastAPI application with GET /health, pyproject.toml, README.md and pytest tests.` Wait for `ready` and expand the generated diffs. The managed project directory remains empty; generated files are only in the isolated proposal workspace.

**Test B — existing project:** Register an existing Python repository. In **Repository Insights**, select a small source file, click **Review selected content**, then **Approve & go to proposals**. Ask Gemini to modify that approved file and add a pytest test. Review the proposed diffs and verify that the original file is unchanged. Modifying or deleting an existing file without explicitly approving its content is rejected.

**Limitations:** This is a proposal generator, not yet the full Analyst → Developer → Tester repository workflow. It does not run tests on generated projects, apply changes, or create a final export. The model can fail to return valid JSON or propose unsupported operations; those failures are reported in the proposal. Snapshots exclude hidden files, symlinks, common secret paths, binary files, and oversized files, but automatic secret exclusion is not a substitute for checking what you approve. Gemini may still be temporarily unavailable. Provider retry events are not yet surfaced individually in the UI.

Backend tests: `uv run pytest -q -m "not integration"`. Frontend: `cd frontend && npm ci && npm run build`. Start the backend with `uv run uvicorn multi_agent_software_team.api.app:app --reload --reload-dir src --host 127.0.0.1 --port 8000` and frontend with `npm run dev`.
