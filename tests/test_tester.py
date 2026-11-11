import ast

from multi_agent_software_team.agents.tester import TesterAgent
from multi_agent_software_team.models import Mission, MissionStatus


def test_tester_generates_test_code():
    """Verify that the tester generates non-empty Python test code.

    The tester is responsible for populating the mission's tests field.
    This test ensures that its output is a non-empty string.
    """
    mission = Mission(description="Create a prime number validator")
    tester = TesterAgent()

    tester.execute(mission)

    assert isinstance(mission.tests, str)
    assert mission.tests.strip()


def test_tester_generates_syntactically_valid_python():
    """Verify that the generated tests contain valid Python syntax.

    The AST parser validates the generated source code without executing
    it. This catches syntax errors independently of test execution.
    """
    mission = Mission(description="Create a prime number validator")
    tester = TesterAgent()

    tester.execute(mission)

    ast.parse(mission.tests)


def test_tester_generates_discoverable_pytest_functions():
    """Verify that generated tests follow pytest naming conventions.

    Pytest discovers module-level functions whose names start with
    'test_'. We inspect the AST to confirm that the generated source
    contains at least one such function.
    """
    mission = Mission(description="Create a prime number validator")
    tester = TesterAgent()

    tester.execute(mission)

    syntax_tree = ast.parse(mission.tests)

    test_functions = [
        node
        for node in syntax_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith("test_")
    ]

    assert test_functions, "No pytest test functions were generated."


def test_tester_preserves_generated_code():
    """Verify that the tester does not overwrite developer output.

    The tester receives a mission containing generated source code.
    It must preserve that implementation while adding its own tests.
    """
    generated_code = "def is_prime(number: int) -> bool:\n    return number > 1"

    mission = Mission(
        description="Create a prime number validator",
        code=generated_code,
    )

    tester = TesterAgent()
    tester.execute(mission)

    assert mission.code == generated_code


def test_tester_preserves_existing_requirements():
    """Verify that the tester preserves requirements from the analyst.

    Requirements remain part of the shared mission state and must not
    be modified when the tester generates its test cases.
    """
    requirements = [
        "Implement a prime number validator.",
        "Handle numbers smaller than two.",
    ]

    mission = Mission(
        description="Create a prime number validator",
        requirements=requirements.copy(),
    )

    tester = TesterAgent()
    tester.execute(mission)

    assert mission.requirements == requirements


def test_tester_does_not_modify_unrelated_mission_fields():
    """Verify that the tester only modifies its assigned output field.

    Mission status and execution metadata are controlled by the
    orchestrator, not by the individual tester agent.
    """
    mission = Mission(description="Create a prime number validator")
    tester = TesterAgent()

    tester.execute(mission)

    assert mission.description == "Create a prime number validator"
    assert mission.status == MissionStatus.PENDING
    assert mission.code == ""
    assert mission.feedback == ""
    assert mission.attempts == 0