from dotenv import load_dotenv
from multi_agent_software_team.llm.gemini import GeminiClient
from multi_agent_software_team.models import Mission
from multi_agent_software_team.orchestrator import Orchestrator

def main() -> None:
    """Run an example mission using Gemini for requirements analysis."""

    load_dotenv()
    
    mission = Mission(
        description="Create a Python function that checks if a number is prime."
    )

    orchestrator = Orchestrator(llm=GeminiClient())
    result = orchestrator.run(mission)

    print("\nMission result:")
    print(f"Status: {result.status.value}")
    print("\nRequirements:")

    for requirement in result.requirements:
        print(f"- {requirement}")

    print(f"\nGenerated code:\n{result.code}")
    print(f"\nGenerated tests:\n{result.tests}")


if __name__ == "__main__":
    main()