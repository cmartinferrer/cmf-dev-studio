from unittest.mock import Mock

import pytest

from multi_agent_software_team.llm.gemini import GeminiClient


def test_gemini_client_generates_text():
    """Verify that GeminiClient returns the generated text.

    The underlying SDK is mocked to avoid network requests.
    This test checks that the client converts the provider's
    response into the string expected by our LLM interface.
    """
    sdk_client = Mock()
    sdk_client.models.generate_content.return_value.text = (
        "Generated requirements"
    )

    client = GeminiClient(
        model="gemini-2.5-flash",
        sdk_client=sdk_client,
    )

    result = client.generate("Analyze this mission")

    assert result == "Generated requirements"


def test_gemini_client_passes_model_and_prompt():
    """Verify that Gemini receives the configured model and prompt.

    The adapter must forward the original prompt unchanged and
    use the model selected during initialization.
    """
    sdk_client = Mock()
    sdk_client.models.generate_content.return_value.text = "Response"

    client = GeminiClient(
        model="gemini-2.5-flash",
        sdk_client=sdk_client,
    )

    client.generate("Create a Python function")

    sdk_client.models.generate_content.assert_called_once_with(
        model="gemini-2.5-flash",
        contents="Create a Python function",
    )


def test_gemini_client_rejects_empty_response():
    """Verify that an empty model response raises a clear error.

    A missing response must not be treated as successful generation.
    This prevents downstream agents from receiving invalid output.
    """
    sdk_client = Mock()
    sdk_client.models.generate_content.return_value.text = None

    client = GeminiClient(
        model="gemini-2.5-flash",
        sdk_client=sdk_client,
    )

    with pytest.raises(ValueError, match="empty response"):
        client.generate("Analyze this mission")