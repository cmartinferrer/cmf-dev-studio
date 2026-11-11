"""Sequential orchestration with optional test validation and retries."""

from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.agents.tester import TesterAgent
from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.runner.client import TestRunner
from multi_agent_software_team.runner.models import TestResult, TestStatus


class Orchestrator:
    """Coordinate agents and retry implementations after test failures."""

    def __init__(
        self,
        llm: LLMClient,
        runner: TestRunner | None = None,
        max_attempts: int = 3,
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
        print("[Orchestrator] Starting mission...")
        mission.status = MissionStatus.IN_PROGRESS
        mission.feedback = ""
        mission.attempts = 0

        try:
            self.analyst.execute(mission)
            self.developer.execute(mission)
            self.tester.execute(mission)

            if self.runner is not None:
                for attempt in range(self.max_attempts):
                    mission.attempts += 1
                    result = self.runner.run(
                        code=mission.code,
                        tests=mission.tests,
                    )
                    self._apply_test_result(mission, result)

                    if mission.status is MissionStatus.FAILED:
                        if (
                            result.status is TestStatus.TEST_FAILED
                            and attempt + 1 < self.max_attempts
                        ):
                            mission.status = MissionStatus.IN_PROGRESS
                            self.developer.execute(mission)
                            continue

                        print("[Orchestrator] Mission failed during testing.")
                        return mission

                    break

        except Exception as exc:
            mission.status = MissionStatus.FAILED
            mission.feedback = str(exc)
            print(f"[Orchestrator] Mission failed: {exc}")
            return mission

        mission.status = MissionStatus.COMPLETED
        print("[Orchestrator] Mission completed.")
        return mission

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