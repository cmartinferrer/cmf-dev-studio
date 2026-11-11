# Multi-Agent Software Team

An educational multi-agent system built with Python to explore how specialized AI agents collaborate through a central orchestrator to solve software development tasks.

The project is developed incrementally, focusing on multi-agent orchestration, shared state, LLM integration, automated testing, error handling, and isolated code execution without relying on high-level agent frameworks.

## Current Features

- **Mission management:** Shared mission state using Python dataclasses.
- **Analyst Agent:** Generates software requirements dynamically using Google Gemini.
- **Developer Agent:** Generates Python implementations based on the analyst's requirements.
- **Tester Agent:** Generates pytest tests based on the requirements and generated implementation.
- **Orchestrator:** Coordinates agents sequentially, manages mission status, and handles execution failures.
- **LLM abstraction:** Uses an `LLMClient` protocol to decouple agents from specific providers.
- **Gemini integration:** Uses the official Google GenAI SDK.
- **Docker Test Runner:** Executes Python code and pytest tests inside a restricted Docker container.
- **Execution results:** Distinguishes successful tests, test failures, and Docker infrastructure errors.
- **CLI entry point:** Runs an example mission and displays its results.
- **Automated testing:** Includes unit tests with mocks and integration tests using real Docker containers.

> **Current limitation:** The Docker Test Runner is implemented and independently tested, but it is not yet integrated into the orchestrator. Generated code and tests are not automatically executed during the multi-agent workflow.

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
                  Mission Result

       All agents share the same Mission state
                        |
                        v
                    LLMClient
                        |
                        v
                   GeminiClient
                        |
                        v
                   Google Gemini


       Independent Docker Test Runner
                        |
                        v
                 Docker Container
                        |
                        v
                      pytest
                        |
                        v
                    TestResult
```

The orchestrator coordinates three specialized agents:

1. **AnalystAgent:** Analyzes the mission and generates software requirements.
2. **DeveloperAgent:** Implements the requested functionality using those requirements.
3. **TesterAgent:** Generates pytest tests to validate the implementation.

All agents operate on the same `Mission` object, which contains:

- Mission description
- Software requirements
- Generated source code
- Generated tests
- Execution feedback
- Execution attempts
- Current mission status

Each agent accesses the information produced by previous agents.

The agents use the `LLMClient` abstraction to interact with Google Gemini.

The `DockerTestRunner` is currently an independent component responsible for executing Python tests inside a restricted Docker environment. Its integration into the orchestration workflow is planned for a future iteration.

## Requirements

- Python (version specified in `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Google Gemini API key
- Docker with a running daemon (required for Docker integration tests and isolated test execution)

## Getting Started

Clone the repository and install the project dependencies:

```bash
uv sync
```

Create a `.env` file in the project root:

```dotenv
GOOGLE_API_KEY=your_google_api_key
```

The application loads environment variables using `python-dotenv`.

> **Security:** Never commit `.env` or API credentials to version control. Ensure `.env` is included in `.gitignore`.

Run the example mission:

```bash
uv run python main.py
```

The orchestrator executes the following workflow:

1. **AnalystAgent:** Generates software requirements using Gemini.
2. **DeveloperAgent:** Generates Python code using the analyst's requirements.
3. **TesterAgent:** Generates pytest tests based on the requirements and implementation.

The resulting mission contains the requirements, generated code, generated tests, and mission status.

Generated code is displayed but is not automatically executed by the orchestrator.

## LLM Integration

The project uses a provider-independent abstraction for language model interactions.

The `LLMClient` protocol defines a common interface:

```python
from typing import Protocol


class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...
```

The `GeminiClient` implementation adapts the official Google GenAI SDK to this interface.

Agents receive the LLM client through dependency injection, allowing the provider to be replaced without modifying agent implementations.

This design provides several benefits:

- Separation between agent logic and LLM providers.
- Easier integration with alternative language models.
- Deterministic unit testing through mocked LLM responses.
- Reduced coupling between application components.

All three agents use the same `LLMClient` abstraction.

## Mission Lifecycle and Error Handling

The orchestrator manages four mission states:

| Status | Description |
|---|---|
| `PENDING` | The mission has not started. |
| `IN_PROGRESS` | The workflow is running. |
| `COMPLETED` | All agents have executed successfully. |
| `FAILED` | An agent raised an exception. |

If an agent fails, the orchestrator:

1. Stops the workflow.
2. Marks the mission as `FAILED`.
3. Stores the error message in `mission.feedback`.
4. Returns the updated mission.

Previously generated information remains available for inspection.

> **Important:** A `COMPLETED` mission currently means that all agents executed successfully. It does not mean that the generated implementation has passed its tests.

## Docker Test Runner

The project includes a Docker-based test runner for executing Python implementations and pytest tests in a restricted environment.

The runner:

1. Creates a temporary workspace.
2. Writes the Python implementation to `solution.py`.
3. Writes the generated tests to `test_solution.py`.
4. Starts a dedicated Docker container.
5. Executes pytest inside the container.
6. Captures the execution result.
7. Attempts container cleanup and verifies its absence.
8. Removes the temporary workspace.

### Execution Results

`DockerTestRunner.run(code, tests)` returns a `TestResult` containing:

- `success`: Whether execution completed successfully.
- `status`: Classification of the execution outcome.
- `exit_code`: Process exit code.
- `stdout`: Standard output captured from execution.
- `stderr`: Standard error captured from execution.

The supported execution statuses are:

| Status | Description |
|---|---|
| `TestStatus.PASSED` | pytest completed successfully. |
| `TestStatus.TEST_FAILED` | pytest returned a non-zero exit code not recognized as a Docker infrastructure failure. |
| `TestStatus.INFRASTRUCTURE_ERROR` | Docker invocation failure, recognized daemon error, timeout, or unconfirmed container cleanup. |

Docker errors are classified using known exit codes and error messages. Some failures may remain ambiguous.

### Docker Isolation

The runner applies several restrictions to reduce the risks associated with executing Python code:

- Non-root user (`10001:10001`).
- Network access disabled (`--network=none`).
- Read-only container filesystem.
- Linux capabilities dropped.
- Privilege escalation disabled.
- IPC isolation.
- CPU, memory, process, and file descriptor limits.
- Read-only workspace mount.
- Restricted temporary filesystem.
- Python bytecode generation disabled.
- Automatic pytest plugin loading disabled.

The dedicated Docker image is defined in:

```text
docker/test-runner.Dockerfile
```

Build the image using:

```bash
docker build \
  -f docker/test-runner.Dockerfile \
  -t multi-agent-test-runner:latest \
  .
```

### Temporary Workspaces

Execution workspaces are created inside:

```text
.runner-workspaces/
```

Each execution uses a separate temporary directory containing only the Python implementation and its tests:

```text
.runner-workspaces/
└── multi-agent-tests-<unique-id>/
    ├── solution.py
    └── test_solution.py
```

The workspace is mounted into the container in read-only mode.

The project directory itself is not mounted, preventing direct exposure of files such as `.env`, `.git`, and other project resources through this mount.

The `.runner-workspaces/` directory must be excluded from version control:

```gitignore
.runner-workspaces/
```

Temporary workspaces are automatically removed when execution finishes normally.

### Security Limitations

**The Docker Test Runner is not currently approved for executing untrusted LLM-generated code.**

Although Docker restrictions reduce exposure, they do not establish a complete security boundary.

Areas requiring further review include:

- Docker daemon security and container escape risks.
- Host filesystem isolation.
- Container lifecycle management.
- Timeout handling and process termination.
- Cleanup failures.
- Resource exhaustion and denial-of-service risks.

The current integration tests use predefined, trusted Python code.

The runner will not be connected to automatic execution of LLM-generated implementations until the security requirements have been reviewed.

## Development and Testing

The project follows an incremental, test-driven development approach.

Tests cover:

- Mission state and lifecycle.
- Individual agent behavior.
- LLM integration.
- Multi-agent orchestration.
- Error handling.
- Docker command construction and execution result classification.
- Docker container lifecycle management.
- Real Docker integration.

External LLM interactions are mocked during automated testing to avoid API costs and ensure reproducible results.

### Unit Tests

Unit tests use mocks and do not require a running Docker daemon.

Run them with:

```bash
uv run pytest -v -m "not integration"
```

### Docker Integration Tests

Integration tests execute predefined Python code inside real Docker containers.

They verify:

- Successful execution of valid Python code.
- Correct reporting of failing pytest assertions.
- Retrieval of execution results.
- Container cleanup verification.

Before running integration tests, ensure Docker is running and build the runner image:

```bash
docker build \
  -f docker/test-runner.Dockerfile \
  -t multi-agent-test-runner:latest \
  .
```

Run the integration tests:

```bash
uv run pytest -v -m integration
```

### Complete Test Suite

Run all tests with:

```bash
uv run pytest -v
```

**Latest verified results:**

- Unit tests: 69 passed.
- Integration tests: 2 passed.
- Total: 71 passed.

These results reflect the latest local test executions and may change as the project evolves.

## Project Status

**Early development — educational prototype.**

The current implementation demonstrates:

- Shared state between specialized agents.
- Sequential multi-agent orchestration.
- Real LLM integration through Google Gemini.
- Dependency injection and provider abstraction.
- Mission lifecycle management.
- Error handling.
- Docker-based Python test execution.
- Execution result classification.
- Unit and integration testing.

The multi-agent workflow and Docker Test Runner are implemented but are not yet connected.

### Planned Improvements

- Review and strengthen the security of isolated code execution.
- Integrate the Docker Test Runner into the orchestrator.
- Introduce feedback loops between `TesterAgent` and `DeveloperAgent`.
- Implement configurable retry policies.
- Improve logging and execution observability.
- Explore more advanced orchestration strategies.

## License

Not yet specified.