from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.models import Mission


class AnalystAgent:
    """Analyze a mission and generate requirements using an LLM."""

    def __init__(self, llm: LLMClient) -> None:
        """Initialize the analyst with a language model client.

        Args:
            llm: Provider-independent language model client.
        """
        self.llm = llm

    def execute(self, mission: Mission) -> None:
        """Generate requirements from the mission description.

        Args:
            mission: Shared mission state to update.
        """

        prompt = (
            "You are a software requirements analyst.\n"
            "Analyze the following task and produce clear, concise "
            "software requirements.\n"
            "Return one requirement per line, without numbering "
            "or additional explanations.\n\n"
            f"Task: {mission.description}"
        )

        response = self.llm.generate(prompt)

        requirements = [
            line.strip()
            for line in response.splitlines()
            if line.strip()
        ]

        if not requirements:
            raise ValueError("Analyst generated no valid requirements")

        mission.requirements = requirements
