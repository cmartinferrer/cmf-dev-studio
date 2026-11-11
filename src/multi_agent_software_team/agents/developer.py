from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.models import Mission


class DeveloperAgent:
    """Generate Python source code based on mission requirements.

    The developer uses a language model to produce an implementation
    that satisfies the requirements defined by the analyst.

    The LLM dependency is injected through the constructor, keeping
    the agent independent of a specific model provider.
    """

    def __init__(self, llm: LLMClient) -> None:
        """Initialize the developer with a language model client.

        Args:
            llm: Client implementing the LLMClient protocol.
        """
        self.llm = llm

    def execute(self, mission: Mission) -> None:
        """Generate Python code and store it in the shared mission.

        Args:
            mission: Mission containing the description and requirements.
        """
        print("[Developer] Generating implementation...")

        requirements = "\n".join(
            f"- {requirement}"
            for requirement in mission.requirements
        )

        prompt = (
            "You are an experienced Python software developer.\n"
            "Implement the following task according to its requirements.\n"
            "Return only valid Python source code.\n"
            "Do not include Markdown code fences or explanations.\n\n"
            f"Task: {mission.description}\n\n"
            f"Requirements:\n{requirements}"
        )

        code = self.llm.generate(prompt)

        if not code.strip():
            raise ValueError("Developer generated no valid code")

        mission.code = code.strip() + "\n"

        print("[Developer] Implementation generated.")