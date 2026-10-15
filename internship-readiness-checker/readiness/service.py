"""Orchestration: turn a profile + role into a full :class:`Assessment`."""

from __future__ import annotations

from .catalog import role_names
from .models import Assessment, StudentProfile
from .recommendations import build_action_plan, build_insights
from .scoring import score_student


def assess(profile: StudentProfile, role: str, source: str = "student") -> Assessment:
    """Score ``profile`` for ``role`` and attach actions, role fit and insights.

    Raises:
        ValueError: if ``role`` is unknown.
    """
    result = score_student(profile, role)
    actions = build_action_plan(profile, result)
    role_scores = {r: score_student(profile, r).total for r in role_names()}
    insights = build_insights(profile, result, actions, role_scores)
    return Assessment(
        profile=profile,
        role=role,
        result=result,
        actions=actions,
        role_scores=role_scores,
        insights=insights,
        source=source,
    )
