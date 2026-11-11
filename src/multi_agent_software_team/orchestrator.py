from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.agents.tester import TesterAgent
from multi_agent_software_team.models import Mission, MissionStatus
from multi_agent_software_team.llm.client import LLMClient


class Orchestrator:
    def __init__(self, llm: LLMClient) -> None:
        self.analyst = AnalystAgent(llm=llm)
        self.developer = DeveloperAgent()
        self.tester = TesterAgent()

    def run(self, mission: Mission) -> Mission:
        """Execute the multi-agent workflow and manage mission status.

        Agents execute sequentially. If an agent raises an exception,
        the workflow stops and the mission is marked as failed.

        Args:
            mission: Shared mission state.

        Returns:
            The updated mission with its final status and feedback.
        """
        print("[Orchestrator] Starting mission...")

        mission.status = MissionStatus.IN_PROGRESS

        try:
            self.analyst.execute(mission)
            self.developer.execute(mission)
            self.tester.execute(mission)

        except Exception as exc:
            mission.status = MissionStatus.FAILED
            mission.feedback = str(exc)

            print(f"[Orchestrator] Mission failed: {exc}")

            return mission

        mission.status = MissionStatus.COMPLETED

        print("[Orchestrator] Mission completed.")

        return mission