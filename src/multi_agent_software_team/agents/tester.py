from multi_agent_software_team.models import Mission


class TesterAgent:
    def execute(self, mission: Mission) -> None:
        print("[Tester] Generating tests...")

        mission.tests = """
from solution import is_prime


def test_prime_number():
    assert is_prime(7) is True


def test_non_prime_number():
    assert is_prime(8) is False


def test_number_less_than_two():
    assert is_prime(1) is False
""".strip()

        print("[Tester] Tests generated.")