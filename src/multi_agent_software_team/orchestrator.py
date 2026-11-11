
from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.agents.tester import TesterAgent
from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.runner.client import TestRunner
from multi_agent_software_team.runner.models import TestResult, TestStatus


class Orchestrator:
    """Coordinate specialized agents and optional test execution.

    Agents execute sequentially and share a Mission instance.

    When a test runner is provided, the orchestrator validates the
    generated implementation before marking the mission as completed.
    """

    def __init__(
        self,
        llm: LLMClient,
        runner: TestRunner | None = None,
    ) -> None:
        """Initialize agents and optional test execution.

        Args:
            llm: Language model client shared by all three agents.
            runner: Optional test runner used to validate generated code.
        """
        self.analyst = AnalystAgent(llm=llm)
        self.developer = DeveloperAgent(llm=llm)
        self.tester = TesterAgent(llm=llm)
        self.runner = runner

    def run(self, mission: Mission) -> Mission:
        """Execute the multi-agent workflow and manage mission status.

        The workflow runs the analyst, developer, and tester sequentially.
        If a runner is configured, generated code and tests are passed
        to it for validation.

        Any exception stops the workflow and marks the mission as failed.

        Args:
            mission: Shared mission state.

        Returns:
            The updated mission with its final status and feedback.
        """
        print("[Orchestrator] Starting mission...")

        mission.status = MissionStatus.IN_PROGRESS
        mission.feedback = ""

        try:
            self.analyst.execute(mission)
            self.developer.execute(mission)
            self.tester.execute(mission)

            if self.runner is not None:
                mission.attempts += 1

                result = self.runner.run(
                    code=mission.code,
                    tests=mission.tests,
                )

                self._apply_test_result(mission, result)

                if mission.status is MissionStatus.FAILED:
                    print(
                        "[Orchestrator] Mission failed during "
                        f"test execution: {result.status.value}"
                    )
                    return mission

        except Exception as exc:
            mission.status = MissionStatus.FAILED
            mission.feedback = str(exc)

            print(f"[Orchestrator] Mission failed: {exc}")

            return mission

        mission.status = MissionStatus.COMPLETED

        print("[Orchestrator] Mission completed.")

        return mission

    @staticmethod
    def _apply_test_result(
        mission: Mission,
        result: TestResult,
    ) -> None:
        """Apply a test execution result to the mission.

        Args:
            mission: Mission to update.
            result: Result returned by the configured test runner.
        """
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
