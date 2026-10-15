"""Skill-gap analysis, personalised action plan and rule-based insights."""

from __future__ import annotations

import math

from . import config as cfg
from .catalog import get_role, get_skill_info
from .models import ActionItem, StudentProfile, ScoreResult

ROLE_CERTIFICATIONS: dict[str, tuple[str, ...]] = {
    "Data Analyst": (
        "Google Data Analytics Certificate",
        "Microsoft PL-300 (Power BI Data Analyst)",
        "Tableau Desktop Specialist",
    ),
    "ML Engineer": (
        "DeepLearning.AI Machine Learning Specialization",
        "TensorFlow Developer or PyTorch fundamentals badge",
        "AWS Cloud Practitioner (then ML Specialty later)",
    ),
    "Web Developer": (
        "freeCodeCamp Responsive Web Design + JavaScript Algorithms",
        "Meta Front-End Developer Certificate",
        "Google UX Design Certificate",
    ),
    "Backend Developer": (
        "AWS Certified Cloud Practitioner",
        "HackerRank SQL (Advanced) certificate",
        "Linux Foundation intro to Linux (LFS101)",
    ),
}

_PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}
HIGH_IMPACT = 3.5
MEDIUM_IMPACT = 1.5
COMM_TARGET = 80.0
APTITUDE_TARGET = 80.0
CGPA_TARGET = 8.0


def _priority(impact: float) -> str:
    if impact >= HIGH_IMPACT:
        return "High"
    if impact >= MEDIUM_IMPACT:
        return "Medium"
    return "Low"


def _skill_actions(result: ScoreResult) -> list[ActionItem]:
    """One action per missing skill, using the catalog playbook."""
    items: list[ActionItem] = []
    n_req = len(result.matched_required) + len(result.missing_required)
    n_pref = len(result.matched_preferred) + len(result.missing_preferred)
    groups = (
        (result.missing_required, cfg.WEIGHTS[cfg.W_SKILLS] * cfg.REQUIRED_SKILL_SHARE / max(n_req, 1), "required"),
        (
            result.missing_preferred,
            cfg.WEIGHTS[cfg.W_SKILLS] * (1 - cfg.REQUIRED_SKILL_SHARE) / max(n_pref, 1),
            "nice-to-have",
        ),
    )
    for skills, impact, kind in groups:
        for skill in skills:
            info = get_skill_info(skill)
            steps = info.steps if info else (f"Find a free beginner course for {skill} and build one small project.",)
            items.append(
                ActionItem(
                    title=f"Learn {skill} ({kind})",
                    category="skill",
                    impact_points=round(impact, 2),
                    effort_hours=info.hours if info else 20,
                    priority=_priority(impact),
                    steps=steps,
                    project_idea=info.project if info else None,
                    skill=skill,
                )
            )
    return items


def _non_skill_actions(profile: StudentProfile, result: ScoreResult) -> list[ActionItem]:
    """Actions for projects, experience, certifications, soft skills and academics."""
    items: list[ActionItem] = []
    role = result.role

    # Projects -----------------------------------------------------------------
    comp = result.component(cfg.W_PROJECTS)
    if comp.fraction < 1:
        need = cfg.PROJECTS_CAP - int(round(comp.fraction * cfg.PROJECTS_CAP))
        ideas = [
            info.project
            for s in (result.missing_required + result.missing_preferred)[:3]
            if (info := get_skill_info(s)) and info.project
        ]
        idea_line = (
            "Project ideas that also close your skill gaps: " + " | ".join(ideas)
            if ideas
            else f"Pick problems a {role} would solve at work and ship a working demo."
        )
        impact = comp.lost
        items.append(
            ActionItem(
                title=f"Build {need} more role-aligned project{'s' if need != 1 else ''}",
                category="projects",
                impact_points=round(impact, 2),
                effort_hours=25 * need,
                priority=_priority(impact),
                steps=(
                    idea_line,
                    "Give every project a README: problem, approach, results, screenshot and a live demo link.",
                    "Pin the projects on GitHub and add one quantified bullet per project to your resume.",
                ),
            )
        )

    # Experience ---------------------------------------------------------------
    comp = result.component(cfg.W_EXPERIENCE)
    if comp.fraction < 1:
        impact = comp.lost
        items.append(
            ActionItem(
                title="Land an internship or real-world experience",
                category="experience",
                impact_points=round(impact, 2),
                effort_hours=30,
                priority=_priority(impact),
                steps=(
                    "Apply to 10 internships a week (LinkedIn, Internshala, career pages) with a role-tailored resume.",
                    "No offer yet? Do a free virtual internship (e.g. Forage), contribute to open source or join a hackathon and list it as experience.",
                    "Ask the placement cell and alumni for referrals; book 3 short informational chats.",
                ),
            )
        )

    # Certifications -----------------------------------------------------------
    comp = result.component(cfg.W_CERTS)
    if comp.fraction < 1:
        impact = comp.lost
        certs = ROLE_CERTIFICATIONS.get(role, ())
        items.append(
            ActionItem(
                title="Earn a role-relevant certification",
                category="certifications",
                impact_points=round(impact, 2),
                effort_hours=30,
                priority=_priority(impact),
                steps=(
                    "Pick one credential: " + "; ".join(certs) + "." if certs else "Pick one recognised credential for the role.",
                    "Study 4-5 hours a week with the free learning path; pay only for the exam if needed.",
                    "Add the verification link to LinkedIn and the Certifications section of your resume.",
                ),
            )
        )

    # Soft skills ----------------------------------------------------------------
    comm = profile.communication_score
    if comm < COMM_TARGET:
        impact = max(0.0, (COMM_TARGET - comm) / 100.0 * cfg.WEIGHTS[cfg.W_SOFT])
        items.append(
            ActionItem(
                title="Strengthen communication and interview skills",
                category="communication",
                impact_points=round(impact, 2),
                effort_hours=15,
                priority=_priority(impact),
                steps=(
                    "Record a 2-minute self-introduction, review it and iterate until it is clear and structured.",
                    "Practise 5 behavioural questions with the STAR method and do 2 mock interviews (peers or placement cell).",
                    "Present one project demo to a club or class; join Toastmasters or the debate society.",
                ),
            )
        )

    # Academics ----------------------------------------------------------------
    apt = profile.aptitude_score
    if apt < APTITUDE_TARGET:
        impact = max(0.0, (APTITUDE_TARGET - apt) / 100.0 * cfg.APTITUDE_SHARE * cfg.WEIGHTS[cfg.W_ACADEMICS])
        items.append(
            ActionItem(
                title="Raise your aptitude test score",
                category="academics",
                impact_points=round(impact, 2),
                effort_hours=25,
                priority=_priority(impact),
                steps=(
                    "Take a free diagnostic aptitude test and log the topics you miss (quant, logic, verbal).",
                    "Practise 20 questions a day in timed 25-minute sets; review every wrong answer.",
                    "Re-test after 3 weeks and aim for 75+.",
                ),
            )
        )
    if profile.cgpa and profile.cgpa < CGPA_TARGET:
        impact = max(
            0.0,
            (CGPA_TARGET - profile.cgpa)
            / (cfg.CGPA_MAX - cfg.CGPA_FLOOR)
            * cfg.CGPA_SHARE
            * cfg.WEIGHTS[cfg.W_ACADEMICS],
        )
        items.append(
            ActionItem(
                title="Protect and lift your CGPA",
                category="academics",
                impact_points=round(impact, 2),
                effort_hours=40,
                priority=_priority(impact),
                steps=(
                    "Identify the two courses dragging your CGPA down and book faculty office hours.",
                    "Block a weekly 3-hour revision slot and work through past papers.",
                    "Many recruiters use a 6.5-7.5 cut-off, so keep your CGPA above it this semester.",
                ),
            )
        )
    return items


def build_action_plan(profile: StudentProfile, result: ScoreResult) -> list[ActionItem]:
    """Create a prioritised action plan.

    Items are ordered by priority bucket (impact) and, inside a bucket, by
    effort so that quick wins come first.
    """
    items = _skill_actions(result) + _non_skill_actions(profile, result)
    items.sort(key=lambda a: (_PRIORITY_RANK[a.priority], a.effort_hours, -a.impact_points))
    return items


def build_timeline(
    actions: list[ActionItem], hours_per_week: int = 10, max_items: int = 8
) -> list[dict[str, object]]:
    """Lay the top actions out on a weekly calendar.

    Returns one row per action with the weeks it spans, assuming the student
    can invest ``hours_per_week`` hours.
    """
    hours_per_week = max(1, int(hours_per_week))
    rows: list[dict[str, object]] = []
    cursor = 0
    for order, action in enumerate(actions[:max_items], start=1):
        start_week = cursor // hours_per_week + 1
        cursor += action.effort_hours
        end_week = max(start_week, math.ceil(cursor / hours_per_week))
        rows.append(
            {
                "Order": order,
                "Action": action.title,
                "Hours": action.effort_hours,
                "Weeks": f"{start_week}" if start_week == end_week else f"{start_week}-{end_week}",
                "Score impact": f"+{action.impact_points:.1f}",
                "Priority": action.priority,
            }
        )
    return rows


def build_insights(
    profile: StudentProfile,
    result: ScoreResult,
    actions: list[ActionItem],
    role_scores: dict[str, float],
) -> list[str]:
    """Rule-based, deterministic insights shown instantly (no LLM needed)."""
    insights: list[str] = []
    comps = sorted(result.components, key=lambda c: c.fraction, reverse=True)
    strongest, weakest = comps[0], max(result.components, key=lambda c: c.lost)

    insights.append(
        f"**{result.level}** for **{result.role}** with a score of **{result.total:.1f}/100**. "
        f"Strongest area: **{strongest.name}** ({strongest.points:.1f}/{strongest.weight:.0f}); "
        f"biggest loss: **{weakest.name}** (-{weakest.lost:.1f} pts)."
    )

    if result.level != cfg.LEVEL_READY:
        target, label = (
            (cfg.ALMOST_THRESHOLD, cfg.LEVEL_ALMOST)
            if result.total < cfg.ALMOST_THRESHOLD
            else (cfg.READY_THRESHOLD, cfg.LEVEL_READY)
        )
        insights.append(f"You are **{target - result.total:.1f} points** away from **{label}**.")

    if result.missing_required:
        top = result.missing_required[:3]
        gain = sum(a.impact_points for a in actions if a.skill in top)
        insights.append(
            f"You cover **{len(result.matched_required)}/{len(result.matched_required) + len(result.missing_required)}** "
            f"required skills. Closing **{', '.join(top)}** adds about **+{gain:.1f} pts**."
        )
    else:
        insights.append("You cover **all required skills** for this role. Add preferred skills to stand out.")

    quick = [a for a in actions if a.priority in ("High", "Medium")]
    if quick:
        best = min(quick, key=lambda a: a.effort_hours / max(a.impact_points, 0.1))
        insights.append(
            f"Best quick win: **{best.title}** (about {best.effort_hours} h for +{best.impact_points:.1f} pts)."
        )

    if role_scores:
        best_role = max(role_scores, key=role_scores.get)  # type: ignore[arg-type]
        if best_role != result.role and role_scores[best_role] - result.total >= 5:
            insights.append(
                f"Your profile fits **{best_role}** better ({role_scores[best_role]:.1f}) "
                f"than {result.role} ({result.total:.1f}). Consider applying to both."
            )

    if profile.internships == 0:
        insights.append("No internship yet: even one short project-based internship moves you up a full level of experience.")
    return insights


def role_description(role: str) -> str:
    """Short description of a role (empty string if unknown)."""
    try:
        return get_role(role).description
    except ValueError:
        return ""
