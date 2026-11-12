from typing import Protocol


class LLMClient(Protocol):
    """Define the common interface for language model providers.

    Implementations must accept a text prompt and return the
    generated response as a string.

    This abstraction allows agents to work with different
    LLM providers without depending on provider-specific APIs.
    """

    def generate(self, prompt: str) -> str:
        """Generate a text response for the given prompt."""
        ...