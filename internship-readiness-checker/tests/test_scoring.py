"""Unit tests for the explainable readiness scoring function."""

from __future__ import annotations

import math

import pytest

from readiness import config as cfg
from readiness.catalog import get_role
from readiness.models import StudentProfile
from readiness.scoring import level_for, score_student


def _perfect_profile(role: str) -> StudentProfile:
    spec = get_role(role)
    return StudentProfile(
        name="Perfect",
        major="Computer Science",
        cgpa=10.0,
        projects=6,
        internships=3,
        certifications=5,
        communication_score=100,
        aptitude_score=100,
        skills=spec.required + spec.preferred,
    )


def test_perfect_profile_scores_100_and_is_ready() -> None:
    """Test 1: a maximal profile earns every point and the 'Ready' level."""
    result = score_student(_perfect_profile("ML Engineer"), "ML Engineer")
    assert result.total == 100.0
    assert result.level == cfg.LEVEL_READY
    assert not result.missing_required
    assert math.isclose(sum(c.weight for c in result.components), 100.0)


def test_empty_profile_scores_zero_without_crashing() -> None:
    """Test 2: empty / invalid input must never crash and scores 0 'Needs work'."""
    blank = StudentProfile(name="", skills=())
    result = score_student(blank, "Data Analyst")
    assert result.total == 0.0
    assert result.level == cfg.LEVEL_NEEDS_WORK
    assert len(result.missing_required) == len(get_role("Data Analyst").required)

    garbage = StudentProfile(
        name="Bad Data",
        cgpa=float("nan"),
        projects=-3,  # type: ignore[arg-type]
        communication_score=None,  # type: ignore[arg-type]
        aptitude_score="n/a",  # type: ignore[arg-type]
        skills=("not-a-real-skill", ""),
    )
    assert score_student(garbage, "Web Developer").total == 0.0


def test_score_is_role_specific_and_explainable() -> None:
    """Test 3: exact weighted maths, and the same student scores differently per role."""
    student = StudentProfile(
        name="Mid",
        cgpa=7.5,  # (7.5-5)/5 = 0.5
        aptitude_score=50,  # 0.5  -> academics fraction 0.5 -> 7.5 pts
        projects=2,  # 2/4 -> 10 pts
        internships=1,  # 1/2 -> 5 pts
        certifications=1,  # 1/3 -> 1.667 pts
        communication_score=60,  # 9 pts
        skills=("Python", "SQL", "Excel"),  # 3/7 required -> 0.85*3/7*35 = 12.75 pts
    )
    result = score_student(student, "Data Analyst")
    assert result.breakdown[cfg.W_SKILLS] == pytest.approx(12.75)
    assert result.breakdown[cfg.W_PROJECTS] == pytest.approx(10.0)
    assert result.breakdown[cfg.W_ACADEMICS] == pytest.approx(7.5)
    assert result.breakdown[cfg.W_SOFT] == pytest.approx(9.0)
    assert result.breakdown[cfg.W_EXPERIENCE] == pytest.approx(5.0)
    assert result.breakdown[cfg.W_CERTS] == pytest.approx(5 / 3)
    assert result.total == 45.9
    assert result.level == cfg.LEVEL_NEEDS_WORK

    # Same person, different role -> different skills match (Python only overlaps with ML/Backend)
    web = score_student(student, "Web Developer")
    assert web.breakdown[cfg.W_SKILLS] < result.breakdown[cfg.W_SKILLS]
    assert web.total != result.total
    with pytest.raises(ValueError):
        score_student(student, "Astronaut")


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, cfg.LEVEL_READY),
        (75.0, cfg.LEVEL_READY),
        (74.9, cfg.LEVEL_ALMOST),
        (50.0, cfg.LEVEL_ALMOST),
        (49.9, cfg.LEVEL_NEEDS_WORK),
        (0, cfg.LEVEL_NEEDS_WORK),
    ],
)
def test_level_boundaries(score: float, expected: str) -> None:
    """Bonus: Ready is 75+, Almost ready 50-74, Needs work below 50."""
    assert level_for(score) == expected


def test_skill_aliases_are_normalised() -> None:
    """Bonus: 'sklearn', 'postgres' and 'GitHub' count as canonical skills."""
    profile = StudentProfile(skills=("sklearn", "postgres", "GitHub", "Python"))
    result = score_student(profile, "ML Engineer")
    assert "Scikit-learn" in result.matched_required
    assert "Git" in result.matched_required
    backend = score_student(profile, "Backend Developer")
    assert "PostgreSQL" in backend.matched_required
