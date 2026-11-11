# Multi-Agent Software Team

A simple, educational multi-agent system built with Python to demonstrate how specialized AI agents can collaborate through a central orchestrator.

The project is developed incrementally to explore multi-agent orchestration, shared state, LLM integration, testing, and error handling without relying on high-level agent frameworks.

## Current Features

- **Mission management:** Shared mission state using Python dataclasses.
- **Analyst Agent:** Generates software requirements dynamically using Google Gemini.
- **Developer Agent:** Generates Python implementations dynamically using Google Gemini and the analyst's requirements.
- **Tester Agent:** Generates pytest tests dynamically using Google Gemini, based on the mission requirements and generated implementation.
- **Orchestrator:** Coordinates agents sequentially, manages mission status, and handles execution failures.
- **LLM abstraction:** Uses an `LLMClient` protocol to decouple agents from specific providers.
- **Gemini integration:** Uses the official Google GenAI SDK.
- **CLI entry point:** Runs an example mission and displays its results.
- **Automated testing:** Uses pytest and mocks to validate application behavior without external API calls.

> **Current limitations:** All three agents use an LLM, but generated
> code and tests are not executed or validated automatically.
> Mission completion only indicates that the agents finished successfully.

## Architecture

```text
                     User
                       |
                       v
                  Orchestrator
                       |
          +------------+------------+
          |            |            |
          v            v            v
     Analyst Agent  Developer    Tester
          |          Agent        Agent
          v
      LLMClient
          |
          v
     GeminiClient
          |
          v
      Google Gemini

             Shared Mission State
                       |
                       v
                  Mission Result
```

All agents operate on the same `Mission` object, which contains:

- Mission description
- Software requirements
- Generated source code
- Generated tests
- Execution feedback
- Execution attempts
- Current mission status

The orchestrator executes agents sequentially, allowing each agent to access the results produced by previous agents.

## Requirements

- Python (version specified in `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- Google Gemini API key

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
2. **DeveloperAgent:** Generates Python code using Gemini and the analyst's requirements.
3. **TesterAgent:** Generates pytest tests using Gemini, the requirements, and the implementation.

The resulting mission contains the requirements, generated code, tests, and execution status.

## LLM Integration

The project uses a provider-independent abstraction for language model interactions.

The `LLMClient` protocol defines a common interface:

```python
class LLMClient(Protocol):
    def generate(self, prompt: str) -> str:
        ...
```

The `GeminiClient` implementation adapts the official Google GenAI SDK to this interface.

Agents receive the LLM client through dependency injection, allowing the provider to be replaced without modifying the agent's core logic.

This design also enables deterministic unit testing through mocked LLM responses.

All three agents use the same LLMClient abstraction through dependency injection.

## Mission Lifecycle and Error Handling

The orchestrator manages four mission states:

- `PENDING`: The mission has not started.
- `IN_PROGRESS`: The workflow is running.
- `COMPLETED`: All agents have executed successfully.
- `FAILED`: An agent raised an exception.

If an agent fails, the orchestrator:

1. Stops the workflow.
2. Marks the mission as `FAILED`.
3. Stores the error message in `mission.feedback`.
4. Returns the updated mission.

Previously generated information remains available for inspection.

> **Important:** A `COMPLETED` mission currently means that all agents executed successfully, not that the generated code passed its tests.

## Docker test runner outcomes

`DockerTestRunner.run(code, tests)` returns `TestResult` with `status`:

- `TestStatus.PASSED`: pytest exited successfully (code 0).
- `TestStatus.TEST_FAILED`: pytest returned a non-zero exit code not recognized as a Docker failure.
- `TestStatus.INFRASTRUCTURE_ERROR`: Docker invocation/daemon failure, timeout, or unconfirmed container cleanup.

`success`, `exit_code`, `stdout`, and `stderr` are preserved for existing consumers.

**Limitations:** Docker daemon errors are detected using known exit codes and messages; some errors can still be ambiguous. `subprocess.run(timeout=30)` and best-effort cleanup do not provide a proven containment boundary. Do not execute untrusted LLM-generated code until isolation and lifecycle handling are hardened and verified.

## Docker runner hardening

The Docker test runner command uses a non-root UID/GID (`10001:10001`), disables network and IPC access, drops Linux capabilities, disallows privilege escalation, mounts only the generated workspace read-only, limits CPU, memory, PIDs and file descriptors, and disables Python bytecode writes and automatic pytest plugin loading. The Docker image must provide pytest and the configured non-root user.

These settings reduce exposure but **do not make Docker a proven sandbox for hostile code**. The Docker daemon, host filesystem, cleanup failures, timeout semantics, and container escape risks still require security review and a real integration test before running untrusted LLM-generated code. The new unit tests only inspect command arguments and do not start Docker.

## Development and Testing

Run the complete test suite:

```bash
uv run pytest -v
```

The project follows an incremental, test-driven development approach.

Tests cover mission state, individual agents, LLM integration, orchestration, and error handling.

External LLM interactions are mocked during automated testing to avoid API costs and ensure reproducible results.

## Project Status

**Early development — educational prototype.**

The current implementation demonstrates:

- Shared state between specialized agents
- Sequential multi-agent orchestration
- Real LLM integration through Google Gemini
- Dependency injection and provider abstraction
- Mission lifecycle management
- Error handling
- Automated testing

### Planned Improvements

- Execute generated tests in an isolated environment.
- Introduce feedback loops between TesterAgent and DeveloperAgent.
- Implement configurable retry policies.
- Improve logging and execution observability.
- Explore more advanced orchestration strategies.

## License

Not yet specified.