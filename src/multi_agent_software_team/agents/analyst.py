from multi_agent_software_team.models import Mission


class AnalystAgent:
    def execute(self, mission: Mission) -> None:
        print("[Analyst] Analyzing mission...")

        mission.requirements = [
            "Implement the requested functionality in Python.",
            "Handle invalid input appropriately.",
            "Keep the implementation simple and readable.",
            "Ensure the code can be tested automatically.",
        ]

        print("[Analyst] Requirements defined.")