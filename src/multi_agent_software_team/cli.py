"""Command-line entry point for the multi-agent software team."""

import argparse
import sys
from collections.abc import Sequence

from dotenv import load_dotenv
from rich.console import Console
from multi_agent_software_team.presentation import RichPresenter

from multi_agent_software_team.llm.gemini import GeminiClient
from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.orchestrator import Orchestrator
from multi_agent_software_team.runner.docker import DockerTestRunner

DEFAULT_TASK = (
    "Create a Python function called calculate_factorial that accepts "
    "a non-negative integer and returns its factorial. "
    "Raise ValueError for negative numbers."
)


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(description="Run a multi-agent Python development mission.")
    parser.add_argument("task", nargs="?", help="Task description; prompts if omitted.")
    parser.add_argument("--example", action="store_true", help="Use the built-in factorial example.")
    parser.add_argument("--run-tests", dest="run_tests", action="store_true", default=True, help="Execute generated code and tests in Docker (default).")
    parser.add_argument("--generate-only", "--no-run-tests", dest="run_tests", action="store_false", help="Generate code and tests without executing them.")
    parser.add_argument("--max-attempts", type=int, default=3, help="Maximum Docker test executions (default: 3).")
    parser.add_argument("--docker-image", default="multi-agent-test-runner:latest", help="Docker runner image.")
    parser.add_argument("--verbose", action="store_true", help="Show full generated tests and pytest output.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a mission and return a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_attempts < 1:
        parser.error("--max-attempts must be at least 1")
    if args.example and args.task:
        parser.error("Use either a task or --example, not both")

    if args.example:
        description = DEFAULT_TASK
    elif args.task:
        description = args.task.strip()
    elif sys.stdin.isatty():
        try:
            description = input("Describe your Python task: ").strip()
        except EOFError:
            description = ""
    else:
        parser.error("Provide a task or --example when input is not interactive")

    if not description:
        parser.error("Task description cannot be empty")

    if args.run_tests:
        print(
            "Running generated code in a restricted Docker container. "
            "Isolation reduces risk but cannot guarantee safety against malicious code.",
            file=sys.stderr,
        )

    presenter = RichPresenter(Console(), verbose=args.verbose)
    load_dotenv()
    try:
        runner = DockerTestRunner(image=args.docker_image) if args.run_tests else None
        mission = Orchestrator(
            llm=GeminiClient(), runner=runner, max_attempts=args.max_attempts, on_event=presenter
        ).run(Mission(description=description))
    except Exception as exc:
        print(f"Unable to start mission: {exc}", file=sys.stderr)
        return 1

    presenter.show_result(mission, tests_enabled=args.run_tests)
    return 0 if mission.status is MissionStatus.COMPLETED else 1
