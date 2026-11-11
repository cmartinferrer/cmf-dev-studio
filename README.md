# Multi-Agent Software Team

A simple, educational multi-agent system built with Python to demonstrate how specialized AI agents can collaborate through a central orchestrator.

The project is developed incrementally, starting with simulated agents to understand the fundamentals of multi-agent orchestration before integrating real LLMs.

## Current Features

- **Mission management:** shared mission state using Python dataclasses.
- **Analyst Agent:** generates simulated requirements for a mission.
- **Developer Agent:** generates a predefined Python implementation.
- **Tester Agent:** generates predefined unit tests for the implementation.
- **Orchestrator:** coordinates agent execution sequentially and manages mission status.
- **CLI entry point:** runs an example mission and displays its results.

> **Current limitations:** Agents are simulated and do not use an LLM. Generated tests are not executed automatically, and mission completion does not yet imply that the generated code has been validated.

## Architecture

```text
User
  |
  v
Orchestrator
  |
  +--> Analyst Agent
  |
  +--> Developer Agent
  |
  +--> Tester Agent
  |
  v
Mission Result
```

Agents share a `Mission` object containing the description, requirements, generated code, tests, feedback, execution attempts, and current status.

## Requirements

- Python (version specified in `.python-version`)
- [uv](https://docs.astral.sh/uv/)

## Getting Started

Clone the repository and install the project dependencies:

```bash
uv sync
```

Run the example:

```bash
uv run python main.py
```

## Development

Run the project's unit tests:

```bash
uv run pytest
```

## Project Status

**Early development — educational prototype.**

The initial implementation focuses on understanding agent responsibilities, shared state, and sequential orchestration.

Future iterations will introduce real LLM integration, execution of generated tests, feedback loops, and improved error handling.

## License

Not yet specified.
