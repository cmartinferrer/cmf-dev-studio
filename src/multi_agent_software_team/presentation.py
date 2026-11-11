"""Rich terminal adapter for presentation-neutral execution events."""

import difflib
import re

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from multi_agent_software_team.events import EventType, ExecutionEvent
from multi_agent_software_team.models import Mission, MissionStatus


class RichPresenter:
    """Render live mission events, understandable failures, and code revisions."""

    def __init__(self, console: Console, verbose: bool = False) -> None:
        self.console = console
        self.verbose = verbose

    def __call__(self, event: ExecutionEvent) -> None:
        if event.type is EventType.MISSION_STARTED:
            self.console.rule("[bold cyan]Mission started")
        elif event.type is EventType.AGENT_STARTED:
            self.console.print(f"[cyan]→ {event.agent.title()}[/cyan]: working...")
        elif event.type is EventType.AGENT_COMPLETED:
            self.console.print(f"[green]✓ {event.agent.title()}[/green]: completed")
        elif event.type is EventType.TEST_STARTED:
            self.console.print(f"[cyan]→ Docker / pytest[/cyan]: attempt {event.attempt}/{event.max_attempts}")
        elif event.type is EventType.TEST_COMPLETED:
            good = event.status == "passed"
            label = "PASSED" if good else "FAILED"
            self.console.print(f"[{'green' if good else 'red'}]{'✓' if good else '✗'} Docker / pytest: {label}[/] (attempt {event.attempt})")
            if not good and event.message:
                self.console.print(Panel(self._failure_summary(event.message), title="Why did it fail?", border_style="red"))
        elif event.type is EventType.RETRY_STARTED:
            self.console.print(f"[yellow]↻ Retrying with developer feedback[/yellow] (attempt {event.attempt}/{event.max_attempts})")
        elif event.type is EventType.MISSION_COMPLETED:
            self.console.print("[bold green]✓ Mission completed[/bold green]")
        elif event.type is EventType.MISSION_FAILED:
            self.console.print("[bold red]✗ Mission failed[/bold red]")

    @staticmethod
    def _failure_summary(output: str) -> str:
        """Extract a readable pytest failure without relying on truncated summaries."""
        lines = output.splitlines()
        failure_names = [
            line.strip().split(" - ", 1)[0]
            for line in lines if line.startswith("FAILED ")
        ]
        # Pytest's failure body includes the actual assertion or exception on E lines.
        errors = [line.strip()[2:].strip() for line in lines if line.lstrip().startswith("E ")]
        # Some failures only provide the compact short-test summary.
        if not errors:
            errors = [
                line.strip().split(" - ", 1)[1]
                for line in lines if line.startswith("FAILED ") and " - " in line
            ]
        if not errors:
            errors = [
                line.strip() for line in lines
                if re.search(r"(AssertionError|TypeError|Error:|DID NOT RAISE)", line)
            ]
        sections = []
        if failure_names:
            sections.append("Failed tests:\n" + "\n".join(f"• {name}" for name in failure_names[:5]))
        if errors:
            # Keep full error messages; Rich wraps them to the terminal width.
            sections.append("Cause:\n" + "\n".join(errors[-4:]))
        return "\n\n".join(sections) or "Tests failed; use --verbose for full output."

    @staticmethod
    def _code_diff(previous: str, current: str) -> str:
        """Return a unified diff between the code submitted in two attempts."""
        return "".join(difflib.unified_diff(
            previous.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile="previous_attempt.py",
            tofile="corrected_attempt.py",
        ))

    def show_result(self, mission: Mission, tests_enabled: bool) -> None:
        success = mission.status is MissionStatus.COMPLETED
        table = Table(title="Mission summary", show_header=False)
        table.add_column("Field", style="bold")
        table.add_column("Value")
        table.add_row("Status", "COMPLETED" if success else "FAILED")
        table.add_row("Docker executions", str(mission.attempts))
        if mission.history:
            table.add_row("Last test result", mission.history[-1].status.value.upper())
            for attempt in mission.history:
                match = re.search(r"(\d+) passed", attempt.stdout)
                failures = re.search(r"(\d+) failed", attempt.stdout)
                table.add_row(f"Attempt {attempt.number}", f"{attempt.status.value}: {match.group(1) if match else '?'} passed, {failures.group(1) if failures else '0'} failed")
        elif not tests_enabled:
            table.add_row("Validation", "not executed (--generate-only)")
        self.console.print(table)
        self.console.print(Panel("\n".join(f"• {r}" for r in mission.requirements) or "No requirements", title="Analyst requirements"))

        if len(mission.history) > 1:
            self.console.print("[bold]Developer corrections between attempts:[/bold]")
            for previous, current in zip(mission.history, mission.history[1:]):
                diff = self._code_diff(previous.code, current.code)
                title = f"Code changes: attempt {previous.number} → {current.number}"
                if diff:
                    if self.verbose:
                        self.console.print(Panel(Syntax(diff, "diff", word_wrap=True), title=title))
                    else:
                        added = sum(line.startswith("+") and not line.startswith("+++") for line in diff.splitlines())
                        removed = sum(line.startswith("-") and not line.startswith("---") for line in diff.splitlines())
                        self.console.print(f"  Attempt {previous.number} → {current.number}: {added} added, {removed} removed (use --verbose for diff)")
                else:
                    self.console.print(f"  Attempt {previous.number} → {current.number}: no code changes")

        self.console.print(Panel(Syntax(mission.code or "# No code", "python", word_wrap=True), title="Final developer code"))
        if self.verbose:
            self.console.print(Panel(Syntax(mission.tests or "# No tests", "python", word_wrap=True), title="Tester generated tests"))
            for attempt in mission.history:
                self.console.print(Panel(attempt.stdout + "\n" + attempt.stderr, title=f"Pytest output: attempt {attempt.number}"))
        elif mission.history and not success:
            self.console.print(Panel(self._failure_summary(mission.feedback), title="Final failure", border_style="red"))
        self.console.print("[dim]Passing generated tests does not independently prove correctness against all requirements.[/dim]")
