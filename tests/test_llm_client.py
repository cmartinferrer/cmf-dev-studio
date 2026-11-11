from unittest.mock import Mock

from multi_agent_software_team.llm.client import LLMClient


def test_llm_client_accepts_compatible_implementations():
    """Verify that an LLM client can be replaced by a compatible object.

    The application must depend on a common interface rather than
    a specific AI provider.

    Any object implementing generate(prompt: str) -> str should
    be usable as an LLM client.
    """
    client = Mock(spec=LLMClient)
    client.generate.return_value = "Generated response"

    response = client.generate("Explain multi-agent systems")

    assert response == "Generated response"
    client.generate.assert_called_once_with("Explain multi-agent systems")