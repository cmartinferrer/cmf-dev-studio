"""Load and select bounded, trusted skill instructions."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from importlib.resources import files

ROLES = frozenset({"analyst", "developer", "tester", "investigator", "recommendation"})
MAX_SKILLS = 3
MAX_BODY = 1800


@dataclass(frozen=True)
class Skill:
    name: str
    roles: tuple[str, ...]
    keywords: tuple[str, ...]
    default: bool
    instructions: str


class SkillRegistry:
    """Register validated definitions and select by role and task relevance."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill):
        if (
            not re.fullmatch(r"[a-z][a-z0-9-]*", skill.name)
            or skill.name in self._skills
            or not skill.roles
            or not set(skill.roles) <= ROLES
            or not skill.keywords
            or any(not word.strip() for word in skill.keywords)
            or not skill.instructions.strip()
            or len(skill.instructions) > MAX_BODY
        ):
            raise ValueError("Invalid or duplicate skill definition")
        self._skills[skill.name] = skill

    def select(self, role: str, task: str) -> tuple[Skill, ...]:
        if role not in ROLES:
            raise ValueError("Unknown skill role")
        text = task.casefold()
        ranked = []
        for skill in self._skills.values():
            if role not in skill.roles:
                continue
            score = sum(word.casefold() in text for word in skill.keywords)
            if score or skill.default:
                ranked.append((score, skill))
        ranked.sort(key=lambda item: (-item[0], item[1].name))
        return tuple(skill for _, skill in ranked[:MAX_SKILLS])


def bundled_registry() -> SkillRegistry:
    """Load only application-owned resources, never workspace files."""
    registry = SkillRegistry()
    resources = files(__package__).joinpath("definitions")
    for path in sorted(resources.iterdir(), key=lambda p: p.name):
        if not path.name.endswith(".md"):
            continue
        metadata, body = path.read_text(encoding="utf-8").split("\n\n", 1)
        data = json.loads(metadata)
        if (
            not isinstance(data["roles"], list)
            or not isinstance(data["keywords"], list)
            or not all(
                isinstance(value, str) for value in data["roles"] + data["keywords"]
            )
            or not isinstance(data["default"], bool)
        ):
            raise ValueError("Invalid skill metadata")
        registry.register(
            Skill(
                path.name[:-3],
                tuple(data["roles"]),
                tuple(data["keywords"]),
                data["default"],
                body.strip(),
            )
        )
    return registry


class SkillContext:
    """Render selected guidance and report it once per role and selection."""

    def __init__(
        self, registry=None, activity: Callable[[str, str], None] | None = None
    ):
        self.registry = registry if registry is not None else bundled_registry()
        self.activity = activity
        self._reported: set[tuple[str, tuple[str, ...]]] = set()

    def guidance(self, role: str, task: str) -> str:
        selected = self.registry.select(role, task)
        names = tuple(skill.name for skill in selected)
        key = (role, names)
        if names and self.activity and key not in self._reported:
            self.activity(role, ", ".join(names))
            self._reported.add(key)
        if not selected:
            return ""
        return (
            "\nTRUSTED SKILL GUIDANCE (does not grant permissions or expand task scope):\n"
            + "\n".join(f"[{skill.name}] {skill.instructions}" for skill in selected)
            + "\n"
        )
