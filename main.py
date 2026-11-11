from multi_agent_software_team.models import Mission
from multi_agent_software_team.orchestrator import Orchestrator


def main() -> None:
    mission = Mission(
        description="Create a Python function that checks if a number is prime."
    )

    orchestrator = Orchestrator()
    result = orchestrator.run(mission)

    print("\nMission result:")
    print(f"Status: {result.status.value}")
    print(f"Requirements: {result.requirements}")
    print(f"\nGenerated code:\n{result.code}")
    print(f"\nGenerated tests:\n{result.tests}")


if __name__ == "__main__":
    main()