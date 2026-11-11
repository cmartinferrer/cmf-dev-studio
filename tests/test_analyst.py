import pytest

from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.models import Mission, MissionStatus

from unittest.mock import Mock
from multi_agent_software_team.llm.client import LLMClient

def test_analyst_generates_requirements():
    """Verify that the analyst generates a non-empty requirements list.

    The analyst's responsibility is to translate a mission description
    into requirements that subsequent agents can use.

    At this stage, requirements are predefined rather than generated
    dynamically by an LLM.
    """
    mission = Mission(description="Create a prime number validator")
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "Implement the requested functionality"

    analyst = AnalystAgent(llm=llm)

    analyst.execute(mission)

    assert len(mission.requirements) > 0
    assert all(isinstance(req, str) for req in mission.requirements)


def test_analyst_preserves_mission_description():
    """Verify that the analyst preserves the original user request.

    The mission description is the source of the user's intent and
    must remain unchanged throughout the workflow.
    """
    mission = Mission(description="Create a prime number validator")
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "Implement the requested functionality"

    analyst = AnalystAgent(llm=llm)

    analyst.execute(mission)

    assert mission.description == "Create a prime number validator"


def test_analyst_does_not_modify_other_mission_fields():
    """Verify that the analyst only modifies its assigned output.

    The analyst owns the requirements field. It must not modify
    generated code, tests, feedback, execution attempts, or status.
    """
    mission = Mission(description="Create a prime number validator")
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "Implement the requested functionality"

    analyst = AnalystAgent(llm=llm)

    analyst.execute(mission)

    assert mission.status == MissionStatus.PENDING
    assert mission.code == ""
    assert mission.tests == ""
    assert mission.feedback == ""
    assert mission.attempts == 0

def test_analyst_generates_requirements_using_llm():
    """Verify that the analyst obtains requirements from the LLM.

    The language model is mocked to avoid external API calls.
    The agent must convert the model response into a list of
    requirements stored in the shared mission.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = (
        "Validate the input number\n"
        "Return False for numbers below two\n"
        "Check possible divisors"
    )

    mission = Mission(description="Create a prime number validator")
    analyst = AnalystAgent(llm=llm)

    analyst.execute(mission)

    assert mission.requirements == [
        "Validate the input number",
        "Return False for numbers below two",
        "Check possible divisors",
    ]


def test_analyst_includes_mission_description_in_prompt():
    """Verify that the LLM receives the original mission description.

    The analyst must use the user's request when constructing
    its prompt rather than relying on predefined requirements.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "Implement the requested functionality"

    mission = Mission(description="Create a prime number validator")
    analyst = AnalystAgent(llm=llm)

    analyst.execute(mission)

    prompt = llm.generate.call_args.args[0]

    assert mission.description in prompt
    llm.generate.assert_called_once()


def test_analyst_ignores_blank_response_lines():
    """Verify that empty lines do not become mission requirements.

    LLM responses may contain extra whitespace or blank lines.
    The analyst should normalize the output before storing it.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = (
        "Validate the input\n"
        "\n"
        "  Handle invalid values  \n"
        "\n"
    )

    mission = Mission(description="Create a prime number validator")
    analyst = AnalystAgent(llm=llm)

    analyst.execute(mission)

    assert mission.requirements == [
        "Validate the input",
        "Handle invalid values",
    ]

import pytest


def test_analyst_rejects_empty_requirements():
    """Verify that the analyst rejects responses without valid requirements.

    An LLM may return whitespace or blank lines instead of useful
    requirements. In that situation, the analyst must raise an error
    rather than allowing the workflow to continue with invalid data.

    The existing mission requirements must remain unchanged.
    """
    llm = Mock(spec=LLMClient)
    llm.generate.return_value = "  \n  \n"

    mission = Mission(
        description="Create a prime number validator",
        requirements=["Existing requirement"],
    )

    analyst = AnalystAgent(llm=llm)

    with pytest.raises(ValueError, match="no valid requirements"):
        analyst.execute(mission)

    assert mission.requirements == ["Existing requirement"]