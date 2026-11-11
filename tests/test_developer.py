import ast
import pytest

from unittest.mock import Mock

from multi_agent_software_team.llm.client import LLMClient
from multi_agent_software_team.agents.developer import DeveloperAgent
from multi_agent_software_team.models import Mission, MissionStatus


def test_developer_includes_mission_description_in_prompt():
    """Verify that the developer provides mission context to the LLM.

    The generated prompt must contain the original mission description,
    allowing the model to understand the overall development task.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "def example():\n    pass\n"

    mission = Mission(
        description="Create a function that calculates factorials",
        requirements=["Accept a non-negative integer"],
    )

    developer = DeveloperAgent(llm=llm)
    developer.execute(mission)

    prompt = llm.generate.call_args.args[0]

    assert mission.description in prompt


def test_developer_preserves_existing_requirements():
    """Verify that code generation does not modify mission requirements.

    The developer consumes the requirements produced by the analyst
    but must not overwrite or alter them.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "def example():\n    pass\n"

    requirements = [
        "Accept an integer",
        "Return the factorial",
    ]

    mission = Mission(
        description="Create a factorial function",
        requirements=requirements.copy(),
    )

    developer = DeveloperAgent(llm=llm)
    developer.execute(mission)

    assert mission.requirements == requirements


def test_developer_normalizes_generated_code():
    """Verify that generated code has consistent surrounding whitespace.

    The developer removes unnecessary leading and trailing whitespace
    while ensuring that the final source ends with a newline.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = (
        "\n\n  def example():\n"
        "    return True\n\n  "
    )

    mission = Mission(description="Create an example function")

    developer = DeveloperAgent(llm=llm)
    developer.execute(mission)

    assert mission.code == (
        "def example():\n"
        "    return True\n"
    )


def test_developer_rejects_empty_code():
    """Verify that empty LLM responses do not overwrite existing code.

    If the language model returns only whitespace, the developer
    must raise an error and preserve the previous implementation.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = " \n  \n"

    mission = Mission(
        description="Create an example function",
        code="def existing():\n    return True\n",
    )

    developer = DeveloperAgent(llm=llm)

    with pytest.raises(ValueError, match="no valid code"):
        developer.execute(mission)

    assert mission.code == "def existing():\n    return True\n"

def test_developer_generates_code_using_llm():
    """Verify that the developer generates code using an LLM.

    The developer must:
    - Send the mission requirements to the language model.
    - Store the generated source code in the shared mission.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )

    mission = Mission(
        description="Create a function that adds two numbers",
        requirements=[
            "Accept two integer arguments",
            "Return the sum of both arguments",
        ],
    )

    developer = DeveloperAgent(llm=llm)

    developer.execute(mission)

    assert mission.code == (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
    )

    llm.generate.assert_called_once()

    prompt = llm.generate.call_args.args[0]

    assert "Accept two integer arguments" in prompt
    assert "Return the sum of both arguments" in prompt