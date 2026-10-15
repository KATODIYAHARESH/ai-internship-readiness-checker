"""Campus-wide analytics for the placement-cell dashboard."""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import config as cfg
from .models import StudentProfile
from .scoring import score_student

COMPONENT_COLUMNS = {
    cfg.W_SKILLS: "pts_skills",
    cfg.W_PROJECTS: "pts_projects",
    cfg.W_ACADEMICS: "pts_academics",
    cfg.W_SOFT: "pts_soft",
    cfg.W_EXPERIENCE: "pts_experience",
    cfg.W_CERTS: "pts_certs",
}
LEVEL_ORDER = [cfg.LEVEL_READY, cfg.LEVEL_ALMOST, cfg.LEVEL_NEEDS_WORK]


def score_dataframe(students: pd.DataFrame, role_override: str | None = None) -> pd.DataFrame:
    """Score every student.

    Args:
        students: DataFrame from :func:`database.fetch_students_df`.
        role_override: Evaluate everyone against this role; ``None`` uses each
            student's own ``target_role``.

    Returns:
        One row per student with score, level, component points and gaps.
    """
    columns = [
        "id", "name", "major", "year", "evaluated_role", "score", "level", "skills_match_pct",
        *COMPONENT_COLUMNS.values(), "weakest_area", "missing_required", "cgpa", "projects",
        "internships", "certifications", "communication_score", "aptitude_score",
    ]
    if students is None or students.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for rec in students.to_dict("records"):
        profile = StudentProfile.from_mapping(rec)
        role = role_override or profile.target_role
        if not role:
            continue
        res = score_student(profile, role)
        row: dict[str, Any] = {
            "id": profile.student_id,
            "name": profile.name,
            "major": profile.major,
            "year": rec.get("year"),
            "evaluated_role": role,
            "score": res.total,
            "level": res.level,
            "skills_match_pct": round(res.skills_match_pct, 1),
            "weakest_area": max(res.components, key=lambda c: c.lost).name,
            "missing_required": list(res.missing_required),
            "cgpa": profile.cgpa,
            "projects": profile.projects,
            "internships": profile.internships,
            "certifications": profile.certifications,
            "communication_score": profile.communication_score,
            "aptitude_score": profile.aptitude_score,
        }
        for comp in res.components:
            row[COMPONENT_COLUMNS[comp.name]] = round(comp.points, 2)
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def campus_kpis(scored: pd.DataFrame) -> dict[str, float]:
    """Headline KPIs. Returns zeros for an empty frame."""
    n = len(scored)
    if n == 0:
        return {"students": 0, "avg_score": 0.0, "median_score": 0.0, "pct_ready": 0.0, "pct_almost": 0.0, "pct_needs_work": 0.0, "at_risk": 0}
    levels = scored["level"]
    return {
        "students": n,
        "avg_score": round(float(scored["score"].mean()), 1),
        "median_score": round(float(scored["score"].median()), 1),
        "pct_ready": round(100 * float((levels == cfg.LEVEL_READY).mean()), 1),
        "pct_almost": round(100 * float((levels == cfg.LEVEL_ALMOST).mean()), 1),
        "pct_needs_work": round(100 * float((levels == cfg.LEVEL_NEEDS_WORK).mean()), 1),
        "at_risk": int((levels == cfg.LEVEL_NEEDS_WORK).sum()),
    }


def level_distribution(scored: pd.DataFrame) -> pd.DataFrame:
    """Counts per readiness level in a fixed order."""
    counts = scored["level"].value_counts() if len(scored) else pd.Series(dtype=int)
    return pd.DataFrame({"level": LEVEL_ORDER, "students": [int(counts.get(lv, 0)) for lv in LEVEL_ORDER]})


def by_department(scored: pd.DataFrame) -> pd.DataFrame:
    """Average score, % ready and % at risk per department/major."""
    if scored.empty:
        return pd.DataFrame(columns=["major", "students", "avg_score", "pct_ready", "pct_at_risk"])
    grouped = scored.groupby("major")
    out = pd.DataFrame(
        {
            "students": grouped.size(),
            "avg_score": grouped["score"].mean().round(1),
            "pct_ready": grouped["level"].apply(lambda s: round(100 * (s == cfg.LEVEL_READY).mean(), 1)),
            "pct_at_risk": grouped["level"].apply(lambda s: round(100 * (s == cfg.LEVEL_NEEDS_WORK).mean(), 1)),
        }
    )
    return out.reset_index().sort_values("avg_score", ascending=False, ignore_index=True)


def component_averages(scored: pd.DataFrame) -> pd.DataFrame:
    """Average points earned per component versus its maximum weight."""
    rows = []
    for name, col in COMPONENT_COLUMNS.items():
        avg = float(scored[col].mean()) if len(scored) else 0.0
        rows.append({"component": name, "avg_points": round(avg, 2), "max_points": cfg.WEIGHTS[name]})
    return pd.DataFrame(rows)


def top_skill_gaps(scored: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Most frequently missing *required* skills across the filtered cohort."""
    if scored.empty:
        return pd.DataFrame(columns=["skill", "students_missing", "pct_students"])
    exploded = scored[["id", "missing_required"]].explode("missing_required").dropna(subset=["missing_required"])
    if exploded.empty:
        return pd.DataFrame(columns=["skill", "students_missing", "pct_students"])
    counts = exploded["missing_required"].value_counts().head(top_n)
    out = counts.rename_axis("skill").reset_index(name="students_missing")
    out["pct_students"] = (100 * out["students_missing"] / len(scored)).round(1)
    return out


def at_risk_students(scored: pd.DataFrame, threshold: float = cfg.ALMOST_THRESHOLD) -> pd.DataFrame:
    """Students scoring below ``threshold``, lowest first, with the main reason."""
    cols = ["name", "major", "evaluated_role", "score", "weakest_area", "top_missing_skills"]
    if scored.empty:
        return pd.DataFrame(columns=cols)
    risk = scored[scored["score"] < threshold].copy()
    risk["top_missing_skills"] = risk["missing_required"].apply(lambda m: ", ".join(m[:3]))
    return risk.sort_values("score", ignore_index=True)[cols]


def campus_insights(scored: pd.DataFrame, gaps: pd.DataFrame, depts: pd.DataFrame) -> list[str]:
    """Plain-English observations for placement officers (rule-based)."""
    if scored.empty:
        return ["No students match the current filters."]
    k = campus_kpis(scored)
    out = [
        f"**{k['pct_ready']:.0f}%** of {k['students']} students are *Ready*, **{k['pct_almost']:.0f}%** are *Almost ready* "
        f"and **{k['pct_needs_work']:.0f}%** need focused support (average score {k['avg_score']:.1f})."
    ]
    if not gaps.empty:
        top = gaps.iloc[0]
        out.append(
            f"The biggest campus-wide gap is **{top['skill']}**: {top['pct_students']:.0f}% of students lack it. "
            f"A single workshop here would lift the most students."
        )
    if len(depts) > 1:
        best, worst = depts.iloc[0], depts.iloc[-1]
        out.append(
            f"**{best['major']}** leads (avg {best['avg_score']:.1f}) while **{worst['major']}** trails "
            f"(avg {worst['avg_score']:.1f}); consider cross-department bootcamps."
        )
    comp = component_averages(scored)
    comp["pct"] = comp["avg_points"] / comp["max_points"]
    weakest = comp.sort_values("pct").iloc[0]
    out.append(
        f"Across the cohort **{weakest['component']}** is weakest ({100 * weakest['pct']:.0f}% of available points)."
    )
    return out


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialise a DataFrame to UTF-8 CSV, flattening list columns."""
    flat = df.copy()
    for col in flat.columns:
        if flat[col].map(lambda v: isinstance(v, (list, tuple))).any():
            flat[col] = flat[col].map(lambda v: "; ".join(v) if isinstance(v, (list, tuple)) else v)
    return flat.to_csv(index=False).encode("utf-8")
