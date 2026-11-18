"""Provider- and language-independent workflow contracts for repository workflows.

No code execution or repository writes occur in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentRole(str, Enum):
    ANALYST = "analyst"
    DEVELOPER = "developer"
    TESTER = "tester"


@dataclass(frozen=True)
class WorkflowPolicy:
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")

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
    if any(p.endswith(".py") for p in paths):
        languages.append("Python")
    if any(p.endswith(".java") for p in paths) or "pom.xml" in paths:
        languages.append("Java")
    if any(p.endswith((".kt", ".kts")) for p in paths):
        languages.append("Kotlin")
    if any(p.endswith((".ts", ".tsx", ".js", ".jsx")) for p in paths):
        languages.append("JavaScript/TypeScript")
    if any(p.endswith(".go") for p in paths):
        languages.append("Go")
    if any(p.endswith(".rs") for p in paths):
        languages.append("Rust")
    adapter = "python-pytest" if languages == ["Python"] else None
    return TechnologyProfile(tuple(languages), adapter)


def acceptance_guidance() -> str:
    return (
        "Acceptance criteria must be externally observable and independent of implementation. "
        "Tests must assert concrete expected outputs from requirements or approved configuration, "
        "not compare an endpoint to the same helper used by its implementation. "
        "Do not invent expected values when required configuration was not approved. "
        "Preserve every explicit user requirement, including real external effects and failure behavior. "
        "A log message, stub, fake success or mock in production is not a substitute for a requested effect. "
        "Use mocks only at test boundaries; verify the production path invokes the real integration. "
        "Declare necessary runtime dependencies and report unavailable capabilities explicitly. "
        "Prefer the simplest complete solution; do not add unrelated features."
    )


def test_quality_guidance() -> str:
    """Shared, language-independent test design and review policy."""
    return (
        "Map every testable acceptance criterion to a concrete behavioral assertion; "
        "one test may cover multiple criteria. Verify actual values, persisted contents, "
        "and relevant external calls with their arguments, counts and order when required. "
        "For repeated behavior, exercise multiple iterations and controlled termination; "
        "a single iteration cannot prove repetition. Cover relevant failure paths and "
        "boundary cases without inventing requirements. Use deterministic clocks, scoped mocks "
        "and temporary resources; restore global state even when assertions fail. "
        "Do not mutate global module registries at test import time or use fixed shared output files. "
        "Avoid real sleeps, network calls and hardware effects in unit tests; mock only external "
        "boundaries, not the behavior under test. Distinguish unit tests from integration checks "
        "that require an external environment. Ask whether removing a required behavior would "
        "make a test fail; flag missing assertions, tautologies and swallowed unexpected errors. "
        "During repair preserve valid assertions and coverage; correct a test only when its "
        "expectation contradicts the original requirements. Prefer existing test conventions "
        "and the smallest sufficient suite; no arbitrary coverage percentage or unrelated tests."
    )


def recommendation_guidance() -> str:
    """Evaluate optional improvements without expanding the requested patch."""
    return (
        "Explicitly evaluate the approved code for one concrete optional improvement "
        "directly related to the task. Compare existing sibling symbols with the "
        "requested naming and style; consider reuse, duplication and related test gaps. "
        "For example, if new methods must follow a naming convention and an existing "
        "peer violates it, recommend aligning that peer, citing its actual name. "
        "Return recommendation as a concise string naming the affected symbol or file "
        "and explaining why; return an empty string only if no relevant evidence exists. "
        "Use the user's language. Never implement optional advice, add it to requirements "
        "or report it as a blocking issue. Do not explore solely to find advice."
    )


def normalize_recommendation(value: object) -> str:
    """Ignore malformed optional advice without rejecting the main response."""
    return value.strip()[:600] if isinstance(value, str) else ""


def code_awareness_guidance() -> str:
    """Shared evidence and scope policy for repository changes."""
    return (
        "Infer naming, architecture, reusable helpers and test conventions from "
        "approved source, not filenames or language stereotypes. Respect explicit "
        "user conventions for new code even if existing code differs. Reuse existing "
        "implementations when appropriate. Before changing a public symbol or contract, "
        "identify callers, imports, exports and tests; do not assume references are "
        "complete without evidence. Preserve existing behavior and unrelated code. "
        "Treat optional consistency improvements as separate from required changes; "
        "do not silently rename or refactor unrelated existing symbols."
    )
