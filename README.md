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
- **CLI entry point:** Runs an example mission and displays its results.
- **Automated testing:** Includes mocked unit tests and integration tests using real Docker containers with predefined, trusted code.

> **Current limitation:** The orchestrator can use an injected `TestRunner`, but the CLI does not configure one. LLM-generated code is not automatically executed. Docker isolation has not been approved as a security boundary for untrusted code.

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

The agents use the `LLMClient` abstraction to communicate with Gemini. An optional `TestRunner` can validate the generated code after all agents finish. On test failures, the developer may regenerate the implementation using feedback while the original tests remain unchanged. **In the CLI, no runner is configured**, so the example workflow only generates code and tests.

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

The orchestrator runs `AnalystAgent`, `DeveloperAgent`, and `TesterAgent` sequentially. The resulting mission contains requirements, generated code, tests, and execution status. The CLI displays the generated artifacts but does not run them.

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

The last confirmed baseline before optional orchestrator-runner integration was **69 unit tests and 2 Docker integration tests passing**. The new orchestrator tests must be run locally before recording an updated total.

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