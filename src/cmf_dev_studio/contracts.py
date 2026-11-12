"""Structured agent response contracts."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass

def parse_json(text: str) -> dict:
    raw = text.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.I).strip()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Expected a JSON object')
    return value


PATCH_SCHEMA = {"type": "object", "properties": {"operations": {"type": "array", "items": {"type": "object", "properties": {"action": {"type": "string", "enum": ["create", "modify", "delete"]}, "path": {"type": "string"}, "content": {"type": "string"}}, "required": ["action", "path", "content"]}}}, "required": ["operations"]}
PLAN_SCHEMA = {"type": "object", "properties": {key: {"type": "array", "items": {"type": "string"}} for key in ("requirements", "acceptance")}, "required": ["requirements", "acceptance"]}
REVIEW_SCHEMA = {"type": "object", "properties": {"issues": {"type": "array", "items": {"type": "string"}}}, "required": ["issues"]}


def structured_response(llm, prompt: str, schema: dict) -> dict:
    # Optional provider capability; text-only adapters still undergo validation.
    method = getattr(type(llm), 'generate_json', None)
    return parse_json(llm.generate_json(prompt, schema) if callable(method) else llm.generate(prompt))


@dataclass(frozen=True)
class Plan:
    requirements: tuple[str, ...]
    acceptance: tuple[str, ...]


