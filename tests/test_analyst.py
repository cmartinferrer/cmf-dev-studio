from multi_agent_software_team.agents.analyst import AnalystAgent
from multi_agent_software_team.models import Mission, MissionStatus


def test_analyst_generates_requirements():
    """Verify that the analyst generates a non-empty requirements list.

    The analyst's responsibility is to translate a mission description
    into requirements that subsequent agents can use.

    At this stage, requirements are predefined rather than generated
    dynamically by an LLM.
    """
    mission = Mission(description="Create a prime number validator")
    analyst = AnalystAgent()

    analyst.execute(mission)

    assert len(mission.requirements) > 0
    assert all(isinstance(req, str) for req in mission.requirements)


def test_analyst_preserves_mission_description():
    """Verify that the analyst preserves the original user request.

    The mission description is the source of the user's intent and
    must remain unchanged throughout the workflow.
    """
    mission = Mission(description="Create a prime number validator")
    analyst = AnalystAgent()

    analyst.execute(mission)

    assert mission.description == "Create a prime number validator"


def test_analyst_does_not_modify_other_mission_fields():
    """Verify that the analyst only modifies its assigned output.

    The analyst owns the requirements field. It must not modify
    generated code, tests, feedback, execution attempts, or status.
    """
    mission = Mission(description="Create a prime number validator")
    analyst = AnalystAgent()

    analyst.execute(mission)

    assert mission.status == MissionStatus.PENDING
    assert mission.code == ""
    assert mission.tests == ""
    assert mission.feedback == ""
    assert mission.attempts == 0