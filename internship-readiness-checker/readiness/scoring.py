"""Explainable readiness scoring (0-100), specific to a target role.

Weights (see ``config.WEIGHTS``)::

    Skills match 35 | Projects 20 | Academics 15 | Soft skills 15 | Experience 10 | Certifications 5

Each component is a 0..1 *fraction* multiplied by its weight, so a recruiter or
student can always see exactly where points were won or lost.

The module is pure (no I/O, no Streamlit) which keeps it trivially testable.
"""

from __future__ import annotations

import math
from typing import Any

from . import config as cfg
from .catalog import get_role, normalize_skills
from .models import ComponentScore, ScoreResult, StudentProfile


def _num(value: Any, default: float = 0.0) -> float:
    """Convert to a finite float; ``None``/NaN/garbage become ``default``."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def level_for(score: float) -> str:
    """Map a 0-100 score to Ready (75+), Almost ready (50-74) or Needs work (<50)."""
    if score >= cfg.READY_THRESHOLD:
        return cfg.LEVEL_READY
    if score >= cfg.ALMOST_THRESHOLD:
        return cfg.LEVEL_ALMOST
    return cfg.LEVEL_NEEDS_WORK


def _capped_ratio(count: Any, cap: int) -> float:
    """Diminishing-returns ratio: ``count / cap`` clipped to [0, 1]."""
    return _clamp(max(0.0, _num(count)) / cap)


def score_student(profile: StudentProfile, role: str) -> ScoreResult:
    """Compute the explainable readiness score of ``profile`` for ``role``.

    Args:
        profile: Student data. Missing / invalid numbers are treated as 0.
        role: One of the roles defined in the catalog.

    Returns:
        A :class:`ScoreResult` with the total, level, per-component points and
        the matched / missing skills.

    Raises:
        ValueError: if ``role`` is not a known role.
    """
    spec = get_role(role)
    owned = set(normalize_skills(profile.skills))

    matched_req = tuple(s for s in spec.required if s in owned)
    missing_req = tuple(s for s in spec.required if s not in owned)
    matched_pref = tuple(s for s in spec.preferred if s in owned)
    missing_pref = tuple(s for s in spec.preferred if s not in owned)

    req_cov = len(matched_req) / len(spec.required) if spec.required else 0.0
    pref_cov = len(matched_pref) / len(spec.preferred) if spec.preferred else req_cov
    skills_frac = cfg.REQUIRED_SKILL_SHARE * req_cov + (1 - cfg.REQUIRED_SKILL_SHARE) * pref_cov

    cgpa = _num(profile.cgpa)
    cgpa_norm = _clamp((cgpa - cfg.CGPA_FLOOR) / (cfg.CGPA_MAX - cfg.CGPA_FLOOR))
    aptitude = _clamp(_num(profile.aptitude_score) / 100.0)
    academics_frac = cfg.CGPA_SHARE * cgpa_norm + cfg.APTITUDE_SHARE * aptitude

    comm_frac = _clamp(_num(profile.communication_score) / 100.0)
    projects = max(0, int(_num(profile.projects)))
    internships = max(0, int(_num(profile.internships)))
    certs = max(0, int(_num(profile.certifications)))

    fractions: list[tuple[str, float, str]] = [
        (
            cfg.W_SKILLS,
            skills_frac,
            f"{len(matched_req)}/{len(spec.required)} required and "
            f"{len(matched_pref)}/{len(spec.preferred)} preferred skills for {role}",
        ),
        (
            cfg.W_PROJECTS,
            _capped_ratio(projects, cfg.PROJECTS_CAP),
            f"{projects} project(s); full marks at {cfg.PROJECTS_CAP}+",
        ),
        (
            cfg.W_ACADEMICS,
            academics_frac,
            f"CGPA {cgpa:.2f}/{cfg.CGPA_MAX:.0f} (60%) and aptitude {aptitude * 100:.0f}/100 (40%)",
        ),
        (
            cfg.W_SOFT,
            comm_frac,
            f"Communication score {comm_frac * 100:.0f}/100",
        ),
        (
            cfg.W_EXPERIENCE,
            _capped_ratio(internships, cfg.INTERNSHIPS_CAP),
            f"{internships} internship(s); full marks at {cfg.INTERNSHIPS_CAP}+",
        ),
        (
            cfg.W_CERTS,
            _capped_ratio(certs, cfg.CERTIFICATIONS_CAP),
            f"{certs} certification(s); full marks at {cfg.CERTIFICATIONS_CAP}+",
        ),
    ]

    components = tuple(
        ComponentScore(
            name=name,
            weight=cfg.WEIGHTS[name],
            fraction=frac,
            points=cfg.WEIGHTS[name] * frac,
            detail=detail,
        )
        for name, frac, detail in fractions
    )
    total = round(sum(c.points for c in components), 1)

    return ScoreResult(
        role=role,
        total=total,
        level=level_for(total),
        components=components,
        matched_required=matched_req,
        missing_required=missing_req,
        matched_preferred=matched_pref,
        missing_preferred=missing_pref,
    )
