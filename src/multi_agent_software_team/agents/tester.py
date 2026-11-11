from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.models import Mission


class TesterAgent:
    """Generate pytest tests for the implementation produced by the developer.

    The tester uses a language model to generate tests based on the
    mission requirements and the Python source code.

    The LLM dependency is injected through the constructor, keeping
    the agent independent of a specific model provider.
    """

    def __init__(self, llm: LLMClient) -> None:
        """Initialize the tester with a language model client.

        Args:
            llm: Client implementing the LLMClient protocol.
        """
        self.llm = llm

    def execute(self, mission: Mission) -> None:
        """Generate pytest tests and store them in the shared mission.

        Args:
            mission: Mission containing requirements and generated code.
        """
        print("[Tester] Generating tests...")

        requirements = "\n".join(
            f"- {requirement}"
            for requirement in mission.requirements
        )

        prompt = (
            "You are an experienced Python QA engineer.\n"
            "Write pytest unit tests for the following Python implementation.\n"
            "The tests must validate the software requirements.\n"
            "Include normal cases, edge cases, and error cases.\n"
            "Do not invent requirements or reject valid Python behavior "
            "unless the task explicitly requires it.\n"
            "Import the functions under test from a module named solution.\n"
            "Return only valid Python source code.\n"
            "Do not include Markdown code fences or explanations.\n\n"
            f"Task: {mission.description}\n\n"
            f"Requirements:\n{requirements}\n\n"
            f"Implementation:\n{mission.code}"
        )

        tests = self.llm.generate(prompt)

        if not tests.strip():
            raise ValueError("Tester generated no valid tests")

        mission.tests = tests.strip() + "\n"

        print("[Tester] Tests generated.")