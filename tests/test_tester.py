import ast
import pytest


from unittest.mock import Mock

from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.agents.tester import TesterAgent as AgentUnderTest
from multi_agent_software_team.models import Mission, MissionStatus

def test_tester_includes_mission_description_in_prompt():
    """Verify that the tester includes the mission description.

    The LLM must receive the original task to understand the
    intended behavior of the generated implementation.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "def test_example():\n    assert True\n"

    mission = Mission(description="Create a factorial function")

    tester = AgentUnderTest(llm=llm)
    tester.execute(mission)

    prompt = llm.generate.call_args.args[0]

    assert mission.description in prompt


def test_tester_includes_requirements_in_prompt():
    """Verify that the tester receives the analyst's requirements.

    Requirements define the expected behavior and must be included
    when generating unit tests.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "def test_example():\n    assert True\n"

    mission = Mission(
        description="Create a factorial function",
        requirements=[
            "Return 1 for zero",
            "Raise ValueError for negative numbers",
        ],
    )

    tester = AgentUnderTest(llm=llm)
    tester.execute(mission)

    prompt = llm.generate.call_args.args[0]

    assert "Return 1 for zero" in prompt
    assert "Raise ValueError for negative numbers" in prompt


def test_tester_includes_generated_code_in_prompt():
    """Verify that the tester receives the developer's implementation.

    The generated tests must be based on the actual source code,
    not only on the mission description.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "def test_example():\n    assert True\n"

    code = "def calculate_factorial(n):\n    return 1\n"

    mission = Mission(
        description="Create a factorial function",
        code=code,
    )

    tester = AgentUnderTest(llm=llm)
    tester.execute(mission)

    prompt = llm.generate.call_args.args[0]

    assert code in prompt


def test_tester_preserves_existing_mission_data():
    """Verify that the tester does not modify previous agent outputs.

    The tester may update mission.tests, but the description,
    requirements, and generated implementation must remain unchanged.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "def test_example():\n    assert True\n"

    mission = Mission(
        description="Create a factorial function",
        requirements=["Return 1 for zero"],
        code="def calculate_factorial(n):\n    return 1\n",
    )

    original_description = mission.description
    original_requirements = mission.requirements.copy()
    original_code = mission.code

    tester = AgentUnderTest(llm=llm)
    tester.execute(mission)

    assert mission.description == original_description
    assert mission.requirements == original_requirements
    assert mission.code == original_code


def test_tester_normalizes_generated_tests():
    """Verify that generated tests have consistent surrounding whitespace.

    The tester removes unnecessary leading and trailing whitespace
    while ensuring that the generated source ends with a newline.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = (
        "\n\n  def test_example():\n"
        "    assert True\n\n  "
    )

    mission = Mission(description="Create an example function")

    tester = AgentUnderTest(llm=llm)
    tester.execute(mission)

    assert mission.tests == (
        "def test_example():\n"
        "    assert True\n"
    )


def test_tester_rejects_empty_tests():
    """Verify that empty LLM responses do not overwrite existing tests.

    If the language model returns only whitespace, the tester
    must raise an error and preserve the previous test suite.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = " \n  \n"

    mission = Mission(
        description="Create an example function",
        tests="def test_existing():\n    assert True\n",
    )

    tester = AgentUnderTest(llm=llm)

    with pytest.raises(ValueError, match="no valid tests"):
        tester.execute(mission)

    assert mission.tests == "def test_existing():\n    assert True\n"

def test_tester_generates_tests_using_llm():
    """Verify that the tester generates pytest tests using an LLM.

    The tester must provide the generated implementation and
    mission requirements to the language model, then store
    the generated tests in the shared mission.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = (
        "from solution import calculate_factorial\n\n"
        "def test_factorial_of_zero():\n"
        "    assert calculate_factorial(0) == 1\n"
    )

    mission = Mission(
        description="Create a factorial function",
        requirements=[
            "Accept a non-negative integer",
            "Return the factorial of the input",
            "Raise ValueError for negative numbers",
        ],
        code=(
            "def calculate_factorial(n: int) -> int:\n"
            "    if n < 0:\n"
            "        raise ValueError('Negative input')\n"
            "    result = 1\n"
            "    for i in range(2, n + 1):\n"
            "        result *= i\n"
            "    return result\n"
        ),
    )

    tester = AgentUnderTest(llm=llm)
    tester.execute(mission)

    assert mission.tests == (
        "from solution import calculate_factorial\n\n"
        "def test_factorial_of_zero():\n"
        "    assert calculate_factorial(0) == 1\n"
    )

    llm.generate.assert_called_once()

    prompt = llm.generate.call_args.args[0]

    assert "calculate_factorial" in prompt
    assert "Raise ValueError for negative numbers" in prompt
    assert mission.code in prompt