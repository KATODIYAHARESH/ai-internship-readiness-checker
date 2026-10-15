"""AI mentor: Ollama (llama3.2) with a deterministic rule-based fallback.

The mentor always receives the student's score, level and gaps as grounding
context. If Ollama is not running (or the model is not pulled, or the request
fails) the same question is answered by :func:`rule_based_reply`, so the chat
never breaks on a laptop without a local LLM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Sequence

import requests

from . import config as cfg
from .catalog import get_skill_info, normalize_skills, role_names
from .models import Assessment
from .recommendations import build_timeline
from .resume import extract_skills

logger = logging.getLogger(__name__)

HISTORY_TURNS = 6  # last N messages forwarded to the model


@dataclass(frozen=True)
class OllamaStatus:
    """Result of probing the local Ollama server."""

    online: bool
    model_available: bool
    host: str
    model: str
    detail: str

    @property
    def usable(self) -> bool:
        """True when chat requests can be served by the LLM."""
        return self.online and self.model_available


@dataclass(frozen=True)
class MentorReply:
    """A mentor answer plus where it came from (``ollama`` or ``rule-based``)."""

    text: str
    source: str
    note: str = ""


# --------------------------------------------------------------------------- #
# Ollama plumbing
# --------------------------------------------------------------------------- #
def check_ollama(host: str = cfg.OLLAMA_HOST, model: str = cfg.OLLAMA_MODEL, timeout: float = 1.5) -> OllamaStatus:
    """Probe ``/api/tags`` quickly; never raises."""
    try:
        resp = requests.get(f"{host}/api/tags", timeout=timeout)
        resp.raise_for_status()
        names = [m.get("name", "") for m in resp.json().get("models", [])]
    except (requests.RequestException, ValueError) as exc:
        return OllamaStatus(False, False, host, model, f"Ollama not reachable at {host} ({type(exc).__name__})")
    base = model.split(":")[0]
    has_model = any(n == model or (":" not in model and n.split(":")[0] == base) for n in names)
    detail = f"Model '{model}' ready" if has_model else f"Ollama is running but '{model}' is not pulled (run: ollama pull {model})"
    return OllamaStatus(True, has_model, host, model, detail)


def build_system_prompt(a: Assessment) -> str:
    """Grounding prompt containing the student's score, breakdown and gaps."""
    r = a.result
    breakdown = "; ".join(f"{c.name} {c.points:.1f}/{c.weight:.0f}" for c in r.components)
    top_actions = "; ".join(f"{x.title} (+{x.impact_points:.1f} pts, ~{x.effort_hours}h)" for x in a.actions[:5]) or "none"
    others = ", ".join(f"{k}: {v:.0f}" for k, v in a.role_scores.items())
    p = a.profile
    return (
        "You are a friendly, concise internship-readiness mentor for a university student. "
        "Answer ONLY using the facts below; if something is not covered, say so and give general advice. "
        "Be specific, use short bullet points, and keep answers under 170 words. Never invent scores.\n\n"
        f"STUDENT: {p.name} | major: {p.major} | CGPA {p.cgpa:.2f}/10 | projects {p.projects} | "
        f"internships {p.internships} | certifications {p.certifications} | "
        f"communication {p.communication_score:.0f}/100 | aptitude {p.aptitude_score:.0f}/100\n"
        f"TARGET ROLE: {a.role}\n"
        f"READINESS SCORE: {r.total:.1f}/100 ({r.level})\n"
        f"BREAKDOWN: {breakdown}\n"
        f"SKILLS MATCHED (required): {', '.join(r.matched_required) or 'none'}\n"
        f"SKILLS MISSING (required): {', '.join(r.missing_required) or 'none'}\n"
        f"SKILLS MISSING (preferred): {', '.join(r.missing_preferred) or 'none'}\n"
        f"TOP ACTIONS: {top_actions}\n"
        f"SCORE FOR OTHER ROLES: {others}"
    )


def _chat_ollama(messages: list[dict[str, str]], host: str, model: str, timeout: float) -> str:
    """Single non-streaming chat call. Raises on any failure."""
    resp = requests.post(
        f"{host}/api/chat",
        json={"model": model, "messages": messages, "stream": False, "options": {"temperature": 0.4}},
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.json()["message"]["content"].strip()
    if not content:
        raise ValueError("empty response from model")
    return content


# --------------------------------------------------------------------------- #
# Rule-based fallback
# --------------------------------------------------------------------------- #
def _has(q: str, *words: str) -> bool:
    return any(w in q for w in words)


def _skill_help(skill: str, a: Assessment) -> str:
    info = get_skill_info(skill)
    owned = set(normalize_skills(a.profile.skills))
    if skill in a.result.missing_required:
        status = "is a **required** skill you are still missing"
    elif skill in a.result.missing_preferred:
        status = "is a nice-to-have you are still missing"
    elif skill in owned and skill in (a.result.matched_required + a.result.matched_preferred):
        status = "is already on your profile and counts towards your score"
    elif skill in owned:
        status = "is on your profile but is not scored for this role"
    else:
        status = "is not part of this role's requirements, but is still a useful extra"
    if not info:
        return f"**{skill}** {status}."
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(info.steps, 1))
    return f"**{skill}** {status} for {a.role}. Plan (~{info.hours} h):\n{steps}\n\n**Mini-project:** {info.project}"


def rule_based_reply(question: str, a: Assessment) -> str:
    """Answer ``question`` from the assessment using keyword intents (no LLM)."""
    q = (question or "").lower().strip()
    r = a.result
    p = a.profile

    if not q:
        return "Ask me anything about your score, skill gaps, projects or interview prep."

    mentioned = extract_skills(question)
    if mentioned and _has(q, "learn", "how", "start", "study", "resource", "course", "practice", "improve", "need", "should"):
        return "\n\n".join(_skill_help(s, a) for s in mentioned[:2])

    if _has(q, "which role", "best role", "fit", "switch", "other role", "better role", "suit"):
        ranked = sorted(a.role_scores.items(), key=lambda kv: kv[1], reverse=True)
        lines = "\n".join(f"- **{k}**: {v:.1f}" for k, v in ranked)
        best = ranked[0][0]
        verdict = (
            f"You are already targeting your best-fit role."
            if best == a.role
            else f"**{best}** is currently your strongest fit; applying to it alongside {a.role} widens your chances."
        )
        return f"Your role-specific readiness scores:\n{lines}\n\n{verdict}"

    if _has(q, "plan", "week", "schedule", "roadmap", "timeline", "first", "priorit", "next", "where do i start", "what should i"):
        if not a.actions:
            return "Nothing urgent: your profile is in great shape. Keep polishing projects and mock interviews."
        top = a.actions[:3]
        lines = "\n".join(f"{i}. **{x.title}**: +{x.impact_points:.1f} pts, ~{x.effort_hours} h" for i, x in enumerate(top, 1))
        tl = build_timeline(a.actions, 10, 5)
        weeks = tl[-1]["Weeks"] if tl else "1"
        return (
            f"Start with the highest-impact, lowest-effort items:\n{lines}\n\n"
            f"At ~10 h/week the first {len(tl)} actions take roughly **{weeks} weeks** and could lift you to "
            f"about **{a.potential_score:.0f}/100**. First step: {top[0].steps[0]}"
        )

    if _has(q, "gap", "missing", "lack", "skills do i", "what skills", "weak skill"):
        miss = ", ".join(r.missing_required) or "none"
        pref = ", ".join(r.missing_preferred[:4]) or "none"
        have = ", ".join(r.matched_required) or "none yet"
        return (
            f"For **{a.role}** you have: {have}.\n\n**Missing required:** {miss}\n\n"
            f"**Nice-to-have gaps:** {pref}\n\nAsk 'how do I learn <skill>?' for a step-by-step plan."
        )

    if _has(q, "why", "score", "low", "explain", "breakdown", "weak", "points", "how am i", "result"):
        worst = sorted(r.components, key=lambda c: c.lost, reverse=True)[:3]
        lines = "\n".join(f"- **{c.name}**: {c.points:.1f}/{c.weight:.0f} ({c.detail})" for c in worst)
        return (
            f"Your score is **{r.total:.1f}/100 ({r.level})** for {a.role}. The three biggest point losses:\n{lines}\n\n"
            f"Fixing the top action alone ({a.actions[0].title if a.actions else 'n/a'}) adds about "
            f"+{a.actions[0].impact_points:.1f} pts."
            if a.actions
            else f"Your score is **{r.total:.1f}/100 ({r.level})**; there are no major point losses."
        )

    if _has(q, "project", "portfolio", "github"):
        ideas = [info.project for s in (r.missing_required + r.missing_preferred)[:3] if (info := get_skill_info(s))]
        ideas_txt = "\n".join(f"- {i}" for i in ideas) or f"- Build something a {a.role} would ship at work."
        return (
            f"You have **{p.projects}** project(s); 4+ earns full marks (currently {r.component('Projects').points:.1f}/20).\n"
            f"Projects that also close your gaps:\n{ideas_txt}\n\nAdd a README, a live demo and one quantified result per project."
        )

    if _has(q, "internship", "experience", "apply", "job", "placement", "offer"):
        return (
            f"You have **{p.internships}** internship(s) ({r.component('Experience').points:.1f}/10 points).\n"
            "- Apply to 10 roles a week with a role-tailored resume.\n"
            "- Do a free virtual internship or open-source contribution if you have no offers yet.\n"
            "- Ask alumni and the placement cell for referrals.\n"
            f"Your {r.level.lower()} status means: "
            + ("start applying now." if r.level != "Needs work" else "close the top 2-3 skill gaps first, then apply.")
        )

    if _has(q, "cert", "course", "badge"):
        from .recommendations import ROLE_CERTIFICATIONS

        certs = "\n".join(f"- {c}" for c in ROLE_CERTIFICATIONS.get(a.role, ())) or "- Pick a recognised role-specific credential."
        return f"You hold **{p.certifications}** certification(s). Good options for {a.role}:\n{certs}"

    if _has(q, "communicat", "interview", "soft", "speak", "present", "hr"):
        return (
            f"Your communication score is **{p.communication_score:.0f}/100**.\n"
            "- Record a 2-minute self-introduction and refine it.\n"
            "- Prepare 5 STAR stories (challenge, action, result, learning).\n"
            "- Do 2 mock interviews and present a project demo to a club."
        )

    if _has(q, "cgpa", "gpa", "grade", "academic", "aptitude", "marks"):
        return (
            f"Academics are **{r.component('Academics').points:.1f}/15**: CGPA {p.cgpa:.2f} and aptitude {p.aptitude_score:.0f}/100. "
            "Aptitude is the faster lever: 20 timed questions a day for 3 weeks usually adds 10-15 points."
        )

    if _has(q, "resume", "cv"):
        return (
            "Resume checklist: a Projects section with quantified results, a skills line that mirrors the job description, "
            "GitHub + LinkedIn links and one page. Use the **Resume Analyzer** tab to extract skills and see job-description matches."
        )

    if _has(q, "ready", "level", "chance", "good enough", "am i"):
        nxt = "You are already Ready: start applying." if r.level == cfg.LEVEL_READY else (
            f"You need **{(cfg.READY_THRESHOLD if r.level == cfg.LEVEL_ALMOST else cfg.ALMOST_THRESHOLD) - r.total:.1f} more points** to reach the next level."
        )
        return f"You are **{r.level}** ({r.total:.1f}/100) for {a.role}. {nxt}"

    if re.search(r"\b(hi|hello|hey|help|who are you)\b", q):
        return (
            f"Hi {p.name.split()[0]}! I'm your internship mentor. You scored **{r.total:.1f} ({r.level})** for {a.role}. "
            "Try: *Why is my score low?*, *What should I learn first?*, *How do I learn SQL?* or *Which role fits me best?*"
        )

    return (
        f"You're **{r.level}** ({r.total:.1f}/100) for {a.role}. Your top priority is "
        f"**{a.actions[0].title if a.actions else 'polishing your portfolio'}**. "
        "Ask about your score, skill gaps, a learning plan, projects, internships or which role fits you best."
    )


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def ask_mentor(
    question: str,
    assessment: Assessment,
    history: Sequence[dict[str, str]] = (),
    use_llm: bool = True,
    host: str = cfg.OLLAMA_HOST,
    model: str = cfg.OLLAMA_MODEL,
) -> MentorReply:
    """Answer a question with Ollama when possible, otherwise with rules.

    Args:
        question: The student's message. Empty input returns a gentle prompt.
        assessment: Grounding context (score, gaps, actions).
        history: Previous ``{"role", "content"}`` messages.
        use_llm: Set False to force rule-based mode.
    """
    if not question or not question.strip():
        return MentorReply("Type a question about your readiness, gaps or next steps.", "system")

    note = ""
    if use_llm:
        messages = [{"role": "system", "content": build_system_prompt(assessment)}]
        messages += [{"role": m["role"], "content": m["content"]} for m in list(history)[-HISTORY_TURNS:]]
        messages.append({"role": "user", "content": question.strip()})
        try:
            return MentorReply(_chat_ollama(messages, host, model, cfg.OLLAMA_TIMEOUT), "ollama")
        except (requests.RequestException, ValueError, KeyError) as exc:
            logger.info("Ollama unavailable, using rule-based mentor: %s", exc)
            note = "Ollama is not available, so this answer comes from the built-in rule-based mentor."
    else:
        note = "Rule-based mode is selected."
    return MentorReply(rule_based_reply(question, assessment), "rule-based", note)


def known_roles() -> list[str]:
    """Roles the mentor can talk about (re-exported for the UI)."""
    return role_names()
