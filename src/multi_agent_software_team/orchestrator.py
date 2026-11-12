"""Sequential orchestration with optional test validation and retries."""

from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.agents.tester import TesterAgent
from multi_agent_software_team.events import EventListener, EventType, ExecutionEvent
from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.models import ExecutionAttempt, Mission, MissionStatus
from multi_agent_software_team.runner.client import TestRunner
from multi_agent_software_team.runner.models import TestResult, TestStatus
from multi_agent_software_team.workflow import WorkflowPolicy


class Orchestrator:
    """Coordinate agents and retry implementations after test failures."""

    def __init__(
        self,
        llm: LLMClient,
        runner: TestRunner | None = None,
        max_attempts: int = 3,
        on_event: EventListener | None = None,
    ) -> None:
        """Initialize agents and optional validation.

        Args:
            llm: Language model client shared by the agents.
            runner: Optional test runner; not enabled by default.
            max_attempts: Maximum test executions, including the first.

        Raises:
            ValueError: If max_attempts is less than one.
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self.policy = WorkflowPolicy(max_attempts)

        self.analyst = AnalystAgent(llm=llm)
        self.developer = DeveloperAgent(llm=llm)
        self.tester = TesterAgent(llm=llm)
        self.runner = runner
        self.max_attempts = max_attempts
        self.on_event = on_event

    def run(self, mission: Mission) -> Mission:
        """Compatibility API: delegate to the same engine used by IDE patches."""
        from multi_agent_software_team.unified_engine import UnifiedEngine
        engine = UnifiedEngine(self.analyst.llm, self.policy)
        return engine.run_mission(mission, runner=self.runner, on_event=self.on_event,
                                  agents=(self.analyst, self.developer, self.tester))

    def _emit(self, event_type: EventType, **kwargs: object) -> None:
        """Notify an optional observer without coupling the core to a UI."""
        if self.on_event is not None:
            self.on_event(ExecutionEvent(type=event_type, **kwargs))

    @staticmethod
    def _apply_test_result(mission: Mission, result: TestResult) -> None:
        """Store runner feedback and classify mission success or failure."""
        if result.status is TestStatus.PASSED and result.success:
            mission.feedback = result.stdout
            return

        mission.status = MissionStatus.FAILED
        details = "\n".join(
            part for part in (result.stdout, result.stderr) if part
        )
        mission.feedback = (
            f"Test execution status: {result.status.value}\n"
            f"Exit code: {result.exit_code}\n"
            f"{details}"
        ).strip()