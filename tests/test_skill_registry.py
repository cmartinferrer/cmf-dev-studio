"""Tests for bounded, request-scoped skill selection and agent guidance."""

import json

import pytest

from cmf_dev_studio.agents.investigator import Investigator
from cmf_dev_studio.skills.registry import (
    Skill,
    SkillContext,
    SkillRegistry,
    bundled_registry,
)


def test_bundled_selection():
    """Relevant refactoring guidance outranks default skills."""
    registry = bundled_registry()
    names = [skill.name for skill in registry.select("developer", "rename tests")]
    assert "safe-refactoring" in names
    assert "test-development" in names
    assert len(names) <= 3
    assert "safe-refactoring" not in [
        skill.name for skill in registry.select("recommendation", "rename tests")
    ]


def test_registration_and_budget():
    """New definitions need no orchestrator changes and duplicates fail."""
    registry = SkillRegistry()
    for i in range(5):
        registry.register(
            Skill(f"skill-{i}", ("developer",), ("task",), False, "Guide")
        )
    assert len(registry.select("developer", "task")) == 3
    assert not registry.select("developer", "unrelated")
    with pytest.raises(ValueError):
        registry.register(Skill("skill-0", ("developer",), ("task",), False, "Guide"))
    with pytest.raises(ValueError):
        registry.register(Skill("bad", ("unknown",), ("task",), False, "Guide"))


def test_activity_is_request_scoped():
    """Repeated prompt construction does not duplicate technical events."""
    events = []
    context = SkillContext(activity=lambda *args: events.append(args))
    first = context.guidance("developer", "rename tests")
    assert first == context.guidance("developer", "rename tests")
    assert len(events) == 1
    assert "does not grant permissions" in first
    assert "safe-refactoring" in events[0][1]


def test_investigator_receives_skills_without_extra_model_calls():
    """Skills augment the existing prompt without granting exploration."""
    prompts = []

    class Client:
        def generate(self, prompt):
            prompts.append(prompt)
            return json.dumps(
                {"action": "permission", "query": "", "message": "Explore?"}
            )

    investigator = Investigator(Client(), {}, {}, False, lambda *_: None)
    action, _ = investigator.run("rename a method", [], "English", [])
    assert action == "permission"
    assert not investigator.allowed
    assert len(prompts) == 1
    assert "[safe-refactoring]" in prompts[0]
