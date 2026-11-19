"""Request-scoped optional advice, separate from implementation requirements."""

from dataclasses import dataclass

from cmf_dev_studio.workflow import normalize_recommendation


@dataclass(frozen=True)
class RecommendationContext:
    """Carry bounded candidate evidence between existing agent calls."""

    investigator: str = ""
    developer: str = ""

    def candidates(self) -> list[dict[str, str]]:
        """Return distinct candidates with their origin, never as instructions."""
        result = []
        seen = set()
        for role, value in (
            ("investigator", self.investigator),
            ("developer", self.developer),
        ):
            text = normalize_recommendation(value)
            if text and text.casefold() not in seen:
                result.append({"source": role, "advice": text})
                seen.add(text.casefold())
        return result


@dataclass(frozen=True)
class RecommendationPolicy:
    """Stop unsolicited advice chains while retaining serious-risk review."""

    applying_recommendation: bool = False

    @property
    def critical_only(self) -> bool:
        """Restrict review when the current task implements historical advice."""
        return self.applying_recommendation
