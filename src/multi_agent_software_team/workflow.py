"""Provider- and language-independent workflow contracts shared by IDE and missions.

No code execution or repository writes occur in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentRole(str, Enum):
    ANALYST = 'analyst'
    DEVELOPER = 'developer'
    TESTER = 'tester'


@dataclass(frozen=True)
class WorkflowPolicy:
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10:
            raise ValueError('max_attempts must be between 1 and 10')

    def can_retry(self, attempt: int, *, recoverable: bool) -> bool:
        """Attempt is one-based; infrastructure failures are never retried."""
        return recoverable and 1 <= attempt < self.max_attempts


@dataclass(frozen=True)
class TechnologyProfile:
    languages: tuple[str, ...]
    test_adapter: str | None


def identify_technology(paths: set[str]) -> TechnologyProfile:
    """Detect supported test adapter conservatively; mixed projects are not guessed."""
    languages = []
    if any(p.endswith('.py') for p in paths):
        languages.append('Python')
    if any(p.endswith('.java') for p in paths) or 'pom.xml' in paths:
        languages.append('Java')
    if any(p.endswith(('.kt', '.kts')) for p in paths):
        languages.append('Kotlin')
    if any(p.endswith(('.ts', '.tsx', '.js', '.jsx')) for p in paths):
        languages.append('JavaScript/TypeScript')
    if any(p.endswith('.go') for p in paths):
        languages.append('Go')
    if any(p.endswith('.rs') for p in paths):
        languages.append('Rust')
    adapter = 'python-pytest' if languages == ['Python'] else None
    return TechnologyProfile(tuple(languages), adapter)


def acceptance_guidance() -> str:
    return (
        'Acceptance criteria must be externally observable and independent of implementation. '
        'Tests must assert concrete expected outputs from requirements or approved configuration, '
        'not compare an endpoint to the same helper used by its implementation. '
        'Do not invent expected values when required configuration was not approved.'
    )
