"""Sequential orchestration with optional test validation and retries."""

from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.agents.tester import TesterAgent
from multi_agent_software_team.events import EventListener, EventType, ExecutionEvent
from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.models import ExecutionAttempt, Mission, MissionStatus
from multi_agent_software_team.runner.client import TestRunner
from multi_agent_software_team.runner.models import TestResult, TestStatus


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

        self.analyst = AnalystAgent(llm=llm)
        self.developer = DeveloperAgent(llm=llm)
        self.tester = TesterAgent(llm=llm)
        self.runner = runner
        self.max_attempts = max_attempts
        self.on_event = on_event

    def run(self, mission: Mission) -> Mission:
        """Execute agents and optionally retry failed test executions.

        The analyst and tester run once. The developer runs again only
        after a TEST_FAILED result and only if attempts remain. Docker
        infrastructure errors and unexpected exceptions are not retried.

        Args:
            mission: Shared mission state.

        Returns:
            The updated mission, including execution feedback and status.
        """
        self._emit(EventType.MISSION_STARTED)
        mission.status = MissionStatus.IN_PROGRESS
        mission.feedback = ""
        mission.attempts = 0
        mission.history.clear()

        try:
            for name, agent in (("analyst", self.analyst), ("developer", self.developer), ("tester", self.tester)):
                self._emit(EventType.AGENT_STARTED, agent=name)
                agent.execute(mission)
                self._emit(EventType.AGENT_COMPLETED, agent=name)

            if self.runner is not None:
                for attempt in range(self.max_attempts):
                    mission.attempts += 1
                    submitted_code = mission.code
                    self._emit(EventType.TEST_STARTED, attempt=mission.attempts, max_attempts=self.max_attempts)
                    result = self.runner.run(
                        code=submitted_code,
                        tests=mission.tests,
                    )
                    mission.history.append(
                        ExecutionAttempt(
                            number=mission.attempts,
                            code=submitted_code,
                            status=result.status,
                            exit_code=result.exit_code,
                            stdout=result.stdout,
                            stderr=result.stderr,
                        )
                    )
                    self._apply_test_result(mission, result)
                    self._emit(EventType.TEST_COMPLETED, attempt=mission.attempts, max_attempts=self.max_attempts, status=result.status.value, message=result.stdout if result.status is TestStatus.TEST_FAILED else "")

                    if mission.status is MissionStatus.FAILED:
                        if (
                            result.status is TestStatus.TEST_FAILED
                            and attempt + 1 < self.max_attempts
                        ):
                            mission.status = MissionStatus.IN_PROGRESS
                            self._emit(EventType.RETRY_STARTED, attempt=mission.attempts + 1, max_attempts=self.max_attempts)
                            self._emit(EventType.AGENT_STARTED, agent="developer", attempt=mission.attempts + 1)
                            self.developer.execute(mission)
                            self._emit(EventType.AGENT_COMPLETED, agent="developer", attempt=mission.attempts + 1)
                            continue

                        self._emit(EventType.MISSION_FAILED, message=mission.feedback)
                        return mission

                    break

        except Exception as exc:
            mission.status = MissionStatus.FAILED
            mission.feedback = str(exc)
            self._emit(EventType.MISSION_FAILED, message=str(exc))
            return mission

        mission.status = MissionStatus.COMPLETED
        self._emit(EventType.MISSION_COMPLETED)
        return mission

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