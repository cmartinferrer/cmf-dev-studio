from multi_agent_software_team.models import Mission


class DeveloperAgent:
    def execute(self, mission: Mission) -> None:
        print("[Developer] Implementing solution...")

        mission.code = """
def is_prime(number: int) -> bool:
    if number < 2:
        return False

    for divisor in range(2, int(number ** 0.5) + 1):
        if number % divisor == 0:
            return False

    return True
""".strip()

        print("[Developer] Implementation completed.")