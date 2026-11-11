import ast

from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.models import Mission, MissionStatus


def test_developer_generates_python_code():
    """Verify that the developer produces non-empty Python source code.

    The developer is responsible for populating the mission's code field.
    This test checks that the generated result is a non-empty string.
    """
    mission = Mission(description="Create a prime number validator")
    developer = DeveloperAgent()

    developer.execute(mission)

    assert isinstance(mission.code, str)
    assert mission.code.strip()


def test_developer_generates_syntactically_valid_python():
    """Verify that the generated code can be parsed as valid Python.

    Python's AST parser checks syntax without executing the generated
    code. This allows us to validate its structure safely at this stage.
    """
    mission = Mission(description="Create a prime number validator")
    developer = DeveloperAgent()

    developer.execute(mission)

    ast.parse(mission.code)


def test_developer_preserves_existing_requirements():
    """Verify that the developer does not overwrite analyst requirements.

    Requirements belong to the analyst's output and must remain
    available to subsequent agents throughout the mission lifecycle.
    """
    requirements = [
        "Implement a prime number validator.",
        "Handle numbers smaller than two.",
    ]

    mission = Mission(
        description="Create a prime number validator",
        requirements=requirements.copy(),
    )

    developer = DeveloperAgent()
    developer.execute(mission)

    assert mission.requirements == requirements


def test_developer_does_not_modify_unrelated_mission_fields():
    """Verify that the developer only modifies its assigned output.

    The developer generates source code but must not change the mission
    description, execution status, tests, feedback, or attempt counter.
    """
    mission = Mission(description="Create a prime number validator")
    developer = DeveloperAgent()

    developer.execute(mission)

    assert mission.description == "Create a prime number validator"
    assert mission.status == MissionStatus.PENDING
    assert mission.tests == ""
    assert mission.feedback == ""
    assert mission.attempts == 0