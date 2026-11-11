from multi_agent_software_team.models import Mission, MissionStatus


def test_mission_initial_state():
    """Verify that a new mission starts with the expected default values.

    A newly created mission must be pending, with empty agent outputs
    and no execution attempts. This provides a predictable starting
    state for the orchestrator.
    """
    mission = Mission(description="Create a prime number validator")

    assert mission.description == "Create a prime number validator"
    assert mission.status == MissionStatus.PENDING
    assert mission.requirements == []
    assert mission.code == ""
    assert mission.tests == ""
    assert mission.feedback == ""
    assert mission.attempts == 0


def test_missions_have_independent_requirements():
    """Verify that different missions do not share their requirements.

    Each Mission instance must own an independent requirements list.
    Modifying one mission must not affect another.

    This protects against mutable default value issues in dataclasses.
    """
    first = Mission(description="First mission")
    second = Mission(description="Second mission")

    first.requirements.append("Requirement 1")

    assert first.requirements == ["Requirement 1"]
    assert second.requirements == []


def test_mission_status_can_be_updated():
    """Verify that the mission status can change during its lifecycle.

    The orchestrator is responsible for updating mission status
    as the workflow progresses.
    """
    mission = Mission(description="Test mission")

    mission.status = MissionStatus.IN_PROGRESS

    assert mission.status == MissionStatus.IN_PROGRESS