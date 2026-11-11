# Multi-Agent Software Team

A simple, educational multi-agent system built with Python to demonstrate how specialized AI agents can collaborate through a central orchestrator.

The project is developed incrementally to explore multi-agent orchestration, shared state, LLM integration, testing, and error handling without relying on high-level agent frameworks.

## Current Features

- **Mission management:** Shared mission state using Python dataclasses.
- **Analyst Agent:** Generates software requirements dynamically using Google Gemini.
- **Developer Agent:** Generates a predefined Python implementation.
- **Tester Agent:** Generates predefined pytest tests for the implementation.
- **Orchestrator:** Coordinates agents sequentially, manages mission status, and handles execution failures.
- **LLM abstraction:** Uses an `LLMClient` protocol to decouple agents from specific providers.
- **Gemini integration:** Uses the official Google GenAI SDK.
- **CLI entry point:** Runs an example mission and displays its results.
- **Automated testing:** Uses pytest and mocks to validate application behavior without external API calls.

> **Current limitations:** Only the Analyst Agent uses an LLM. The Developer and Tester agents still generate predefined content. Generated tests are not executed automatically, and mission completion does not yet imply that the generated code has been validated.

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

1. **AnalystAgent:** Analyzes the mission and generates requirements using Gemini.
2. **DeveloperAgent:** Generates a predefined Python implementation.
3. **TesterAgent:** Generates predefined pytest tests.

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

Currently, only the Analyst Agent uses this integration.

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

- Integrate LLM-based code generation into DeveloperAgent.
- Integrate LLM-based test generation into TesterAgent.
- Execute generated tests in an isolated environment.
- Introduce feedback loops between TesterAgent and DeveloperAgent.
- Implement configurable retry policies.
- Improve logging and execution observability.
- Explore more advanced orchestration strategies.

## License

Not yet specified.