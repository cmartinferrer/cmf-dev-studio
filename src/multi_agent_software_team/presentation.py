"""Rich terminal adapter for presentation-neutral execution events."""

import re

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from multi_agent_software_team.events import EventType, ExecutionEvent
from multi_agent_software_team.models import Mission, MissionStatus


class RichPresenter:
    """Render a live mission timeline and a readable final summary."""

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
                summary = self._failure_summary(event.message)
                if summary:
                    self.console.print(Panel(summary, title="Why did it fail?", border_style="red"))
        elif event.type is EventType.RETRY_STARTED:
            self.console.print(f"[yellow]↻ Retrying with developer feedback[/yellow] (attempt {event.attempt}/{event.max_attempts})")
        elif event.type is EventType.MISSION_COMPLETED:
            self.console.print("[bold green]✓ Mission completed[/bold green]")
        elif event.type is EventType.MISSION_FAILED:
            self.console.print("[bold red]✗ Mission failed[/bold red]")

    @staticmethod
    def _failure_summary(output: str) -> str:
        lines = output.splitlines()
        failures = [line.strip() for line in lines if line.startswith("FAILED ")]
        if failures:
            return "\n".join(failures[:3])
        errors = [line.strip() for line in lines if re.search(r"(AssertionError|TypeError|Error:|DID NOT RAISE)", line)]
        return "\n".join(errors[-3:]) or "Tests failed; use --verbose for full output."

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
        self.console.print(Panel(Syntax(mission.code or "# No code", "python", word_wrap=True), title="Final developer code"))
        if self.verbose:
            self.console.print(Panel(Syntax(mission.tests or "# No tests", "python", word_wrap=True), title="Tester generated tests"))
            for attempt in mission.history:
                self.console.print(Panel(attempt.stdout + "\n" + attempt.stderr, title=f"Pytest output: attempt {attempt.number}"))
        elif mission.history and not success:
            self.console.print(Panel(self._failure_summary(mission.feedback), title="Final failure", border_style="red"))
        self.console.print("[dim]Passing generated tests does not independently prove correctness against all requirements.[/dim]")
