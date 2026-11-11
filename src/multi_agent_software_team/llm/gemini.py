from google import genai


class GeminiClient:
    """Adapt the Google Gemini SDK to the application's LLM interface.

    The client exposes a provider-independent generate() method.

    An SDK client can be injected for testing. When omitted,
    the official Google SDK client is initialized using the
    environment's API credentials.
    """

    def __init__(
        self,
        model: str = "gemini-3.5-flash-lite",
        sdk_client: genai.Client | None = None,
    ) -> None:
        """Initialize the Gemini adapter.

        Args:
            model: Gemini model identifier.
            sdk_client: Optional SDK client for dependency injection.
        """
        self.model = model
        self._client = sdk_client if sdk_client is not None else genai.Client()

    def generate(self, prompt: str) -> str:
        """Generate a text response using Gemini.

        Args:
            prompt: Input instructions sent to the language model.

        Returns:
            The generated text.

        Raises:
            ValueError: If Gemini returns an empty text response.
        """
        response = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response")

        return response.text