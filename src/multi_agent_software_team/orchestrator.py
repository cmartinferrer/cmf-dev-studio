from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.agents.tester import TesterAgent
from multi_agent_software_team.models import Mission, MissionStatus


class Orchestrator:
    def __init__(self) -> None:
        self.analyst = AnalystAgent()
        self.developer = DeveloperAgent()
        self.tester = TesterAgent()

    def run(self, mission: Mission) -> Mission:
        print("[Orchestrator] Starting mission...")

        mission.status = MissionStatus.IN_PROGRESS

        self.analyst.execute(mission)
        self.developer.execute(mission)
        self.tester.execute(mission)

        mission.status = MissionStatus.COMPLETED

        print("[Orchestrator] Mission completed.")

        return mission