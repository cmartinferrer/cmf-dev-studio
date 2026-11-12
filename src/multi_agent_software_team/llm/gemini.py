import random
import time
from google import genai


def _transient_error(exc: Exception) -> bool:
    """Retry only provider rate limits and temporary service failures."""
    code = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
    try:
        if int(code) in (429, 500, 502, 503, 504):
            return True
    except (ValueError, TypeError):
        pass
    message = str(exc).upper()
    return any(marker in message for marker in ('429 RESOURCE_EXHAUSTED', '503 UNAVAILABLE', '500 INTERNAL', '502 BAD_GATEWAY', '504 DEADLINE_EXCEEDED'))



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
        max_provider_attempts: int = 3,
        retry_base_seconds: float = 1.0,
    ) -> None:
        """Initialize the Gemini adapter.

        Args:
            model: Gemini model identifier.
            sdk_client: Optional SDK client for dependency injection.
        """
        if max_provider_attempts < 1 or retry_base_seconds < 0:
            raise ValueError('Invalid provider retry settings')
        self.max_provider_attempts = max_provider_attempts
        self.retry_base_seconds = retry_base_seconds
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
        return self._generate(prompt)

    def generate_json(self, prompt: str, schema: dict) -> str:
        return self._generate(prompt, config={"response_mime_type": "application/json", "response_json_schema": schema})

    def _generate(self, prompt: str, **kwargs) -> str:
        for attempt in range(self.max_provider_attempts):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    **kwargs,
                )
                break
            except Exception as exc:
                if not _transient_error(exc) or attempt + 1 == self.max_provider_attempts:
                    raise
                delay = self.retry_base_seconds * (2 ** attempt)
                if delay:
                    time.sleep(delay + random.uniform(0, delay * 0.2))

        if not response.text:
            raise ValueError("Gemini returned an empty response")

        return response.text