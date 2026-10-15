"""Synthetic student generator.

Students are driven by two latent traits (``ability`` and ``drive``) so that
CGPA, skills, projects, internships and certifications are realistically
correlated, while each major has its own role affinity and skill strengths.
The output is deterministic for a given ``seed``.
"""

from __future__ import annotations

import random
from typing import Any

from . import config as cfg
from .catalog import get_role, role_names, skills_info

FIRST_NAMES = [
    "Aarav", "Ananya", "Arjun", "Diya", "Ishaan", "Kavya", "Rohan", "Meera", "Vihaan", "Saanvi",
    "Aditya", "Priya", "Karan", "Neha", "Rahul", "Sneha", "Siddharth", "Tanvi", "Yash", "Pooja",
    "Liam", "Emma", "Noah", "Olivia", "Ethan", "Sophia", "Lucas", "Amelia", "Mateo", "Isabella",
    "Omar", "Fatima", "Wei", "Mei", "Hiro", "Yuki", "Chinedu", "Amara", "Kwame", "Zainab",
    "Daniel", "Sofia", "Mohammed", "Aisha", "Ravi", "Lakshmi", "Nikhil", "Riya", "Farhan", "Zoya",
]
LAST_NAMES = [
    "Sharma", "Patel", "Iyer", "Reddy", "Gupta", "Nair", "Singh", "Mehta", "Kapoor", "Joshi",
    "Khan", "Verma", "Das", "Bose", "Menon", "Rao", "Chopra", "Malhotra", "Bhat", "Pillai",
    "Smith", "Johnson", "Garcia", "Martinez", "Brown", "Nguyen", "Kim", "Tanaka", "Chen", "Wang",
    "Okafor", "Adeyemi", "Hassan", "Ali", "Silva", "Costa", "Novak", "Ivanov", "Rossi", "Muller",
]

# major -> (sampling weight, role affinity, extra-likely skills)
MAJORS: dict[str, dict[str, Any]] = {
    "Computer Science": {
        "weight": 0.27,
        "roles": {"Backend Developer": 0.30, "Web Developer": 0.28, "ML Engineer": 0.20, "Data Analyst": 0.22},
        "boost": ["Python", "Git", "Data Structures", "SQL", "Linux", "JavaScript", "HTML", "CSS"],
        "bonus": 0.08,
    },
    "Information Technology": {
        "weight": 0.18,
        "roles": {"Web Developer": 0.35, "Backend Developer": 0.30, "Data Analyst": 0.25, "ML Engineer": 0.10},
        "boost": ["HTML", "CSS", "JavaScript", "SQL", "Git", "REST APIs", "Linux"],
        "bonus": 0.06,
    },
    "Data Science": {
        "weight": 0.15,
        "roles": {"Data Analyst": 0.40, "ML Engineer": 0.50, "Backend Developer": 0.05, "Web Developer": 0.05},
        "boost": ["Python", "Pandas", "NumPy", "Statistics", "Machine Learning", "Scikit-learn", "Data Visualization"],
        "bonus": 0.10,
    },
    "Business Analytics": {
        "weight": 0.12,
        "roles": {"Data Analyst": 0.85, "ML Engineer": 0.05, "Backend Developer": 0.03, "Web Developer": 0.07},
        "boost": ["Excel", "SQL", "BI Tools", "Statistics", "Data Visualization", "Data Cleaning"],
        "bonus": 0.10,
    },
    "Electronics & Communication": {
        "weight": 0.12,
        "roles": {"Backend Developer": 0.30, "ML Engineer": 0.25, "Data Analyst": 0.25, "Web Developer": 0.20},
        "boost": ["Python", "Linux", "NumPy", "Statistics"],
        "bonus": 0.0,
    },
    "Electrical Engineering": {
        "weight": 0.08,
        "roles": {"Data Analyst": 0.40, "ML Engineer": 0.25, "Backend Developer": 0.20, "Web Developer": 0.15},
        "boost": ["Excel", "Python", "Statistics"],
        "bonus": -0.02,
    },
    "Mechanical Engineering": {
        "weight": 0.08,
        "roles": {"Data Analyst": 0.60, "ML Engineer": 0.15, "Backend Developer": 0.10, "Web Developer": 0.15},
        "boost": ["Excel", "Statistics", "Data Visualization"],
        "bonus": -0.05,
    },
}


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _unique_names(rng: random.Random, n: int) -> list[str]:
    """Return ``n`` distinct 'First Last' names."""
    names: set[str] = set()
    max_unique = len(FIRST_NAMES) * len(LAST_NAMES)
    if n > max_unique:
        raise ValueError(f"Can generate at most {max_unique} unique names")
    while len(names) < n:
        names.add(f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}")
    ordered = sorted(names)
    rng.shuffle(ordered)
    return ordered


def _pick_skills(rng: random.Random, role: str, major: dict[str, Any], ability: float) -> list[str]:
    """Sample a skill set from the target role, the major's strengths and general noise."""
    spec = get_role(role)
    boost = set(major["boost"])
    bonus = float(major["bonus"])
    chosen: set[str] = set()
    for skill in spec.required:
        p = 0.10 + 0.78 * ability + (bonus if skill in boost else bonus / 3)
        if rng.random() < _clip(p, 0.02, 0.97):
            chosen.add(skill)
    for skill in spec.preferred:
        p = 0.04 + 0.50 * ability + (bonus / 2 if skill in boost else 0.0)
        if rng.random() < _clip(p, 0.01, 0.85):
            chosen.add(skill)
    for skill in skills_info():  # adjacent skills from other roles / majors
        if skill in chosen:
            continue
        p = 0.03 + 0.14 * ability + (0.06 if skill in boost else 0.0)
        if rng.random() < _clip(p, 0.0, 0.4):
            chosen.add(skill)
    return sorted(chosen)


def generate_students(count: int = cfg.DEFAULT_STUDENT_COUNT, seed: int = cfg.DEFAULT_SEED) -> list[dict[str, Any]]:
    """Generate ``count`` realistic synthetic students.

    Args:
        count: How many students to create (default 80).
        seed: RNG seed for reproducibility.

    Returns:
        A list of dicts ready for :func:`database.insert_students`.
    """
    if count <= 0:
        return []
    rng = random.Random(seed)
    valid_roles = set(role_names())
    major_names = list(MAJORS)
    weights = [MAJORS[m]["weight"] for m in major_names]
    students: list[dict[str, Any]] = []

    for name in _unique_names(rng, count):
        major = rng.choices(major_names, weights=weights, k=1)[0]
        info = MAJORS[major]
        roles_, role_w = zip(*[(r, w) for r, w in info["roles"].items() if r in valid_roles])
        role = rng.choices(roles_, weights=role_w, k=1)[0]

        ability = _clip(rng.gauss(0.56, 0.22), 0.02, 0.98)
        drive = _clip(0.45 * ability + 0.55 * rng.gauss(0.56, 0.24), 0.0, 1.0)
        year = rng.choices([2, 3, 4], weights=[0.2, 0.4, 0.4], k=1)[0]

        cgpa = _clip(6.1 + 2.5 * ability + rng.gauss(0, 0.40), 5.2, 9.9)
        aptitude = _clip(rng.gauss(32 + 55 * ability, 9), 15, 98)
        communication = _clip(rng.gauss(30 + 40 * drive + 18 * ability, 10), 20, 98)
        projects = int(round(_clip(rng.gauss(0.5 + 3.8 * drive, 0.9), 0, 6)))
        p_intern = _clip(0.05 + 0.85 * drive * (0.6 + 0.2 * year / 2), 0, 0.95)
        internships = (1 if rng.random() < p_intern else 0) + (1 if rng.random() < p_intern * 0.35 else 0)
        certifications = int(round(_clip(rng.gauss(0.3 + 3.0 * drive, 1.0), 0, 6)))

        students.append(
            {
                "name": name,
                "major": major,
                "year": year,
                "cgpa": round(cgpa, 2),
                "projects": projects,
                "internships": internships,
                "certifications": certifications,
                "communication_score": round(communication, 1),
                "aptitude_score": round(aptitude, 1),
                "target_role": role,
                "skills": _pick_skills(rng, role, info, ability),
            }
        )
    return students
