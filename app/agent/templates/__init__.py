"""
Answer templates for the AutoMind agent.

Each template defines:
- name: unique identifier
- sections: ordered list of (title, instructions) for each answer layer
- style: tone and formatting rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class AnswerTemplate:
    name: str
    description: str
    sections: List[Tuple[str, str]] = field(default_factory=list)
    style_rules: List[str] = field(default_factory=list)
    forbidden_patterns: List[str] = field(default_factory=list)


# ── Registry ─────────────────────────────────────────────────

_TEMPLATES: dict = {}


def register(template: AnswerTemplate):
    _TEMPLATES[template.name] = template


def get(name: str) -> AnswerTemplate | None:
    return _TEMPLATES.get(name)


def list_all() -> list:
    return list(_TEMPLATES.values())


# Import templates to trigger registration
from app.agent.templates import car_model, price_trend, comparison, news  # noqa: E402, F401
