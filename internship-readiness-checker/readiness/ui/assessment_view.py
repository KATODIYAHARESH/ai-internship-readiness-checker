"""Shared view that renders one full :class:`Assessment` (used by Student and Resume tabs)."""

from __future__ import annotations

import html
from dataclasses import replace

import pandas as pd
import streamlit as st

from .. import config as cfg
from ..catalog import get_role, normalize_skills
from ..llm import ask_mentor
from ..models import Assessment
from ..recommendations import build_timeline
from ..reports import ReportError, build_markdown_report, build_pdf_report
from ..scoring import score_student
from . import charts
from .components import (
    LEVEL_ICONS,
    PRIORITY_ICONS,
    level_badge,
    safe_filename,
    show_chips,
    signature,
)

COACH_PROMPT = (
    "Write a short, encouraging coaching summary (max 120 words): where I stand, my 3 most valuable next steps "
    "and one thing I am doing well."
)


def render_assessment(a: Assessment, key_prefix: str) -> None:
    """Render metrics, charts and the six detail tabs for ``a``."""
    r = a.result
    sig = signature(a)
    k = f"{key_prefix}_{sig}"

    st.markdown(
        f"### {html.escape(a.profile.name)} &nbsp; {level_badge(r.level)}",
        unsafe_allow_html=True,
    )
    try:
        st.caption(f"**{a.role}**: {get_role(a.role).description}")
    except ValueError:
        st.caption(a.role)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Readiness score", f"{r.total:.1f} / 100", f"{a.potential_score - r.total:+.1f} potential after plan", delta_color="off")
    m2.metric("Level", f"{LEVEL_ICONS.get(r.level, '')} {r.level}")
    m3.metric(
        "Required skills",
        f"{len(r.matched_required)} / {len(r.matched_required) + len(r.missing_required)}",
        f"{r.skills_match_pct:.0f}% match",
        delta_color="off",
    )
    m4.metric("Open actions", len(a.actions), f"{sum(1 for x in a.actions if x.priority == 'High')} high priority", delta_color="off")

    left, right = st.columns([1, 2])
    left.plotly_chart(charts.score_gauge(r.total, r.level), width="stretch", key=f"{k}_gauge")
    right.plotly_chart(charts.breakdown_chart(r), width="stretch", key=f"{k}_breakdown")

    tabs = st.tabs(["🔍 Why this score", "🧩 Skill gaps", "🗺️ Action plan", "🎯 Role fit", "🧪 What-if", "🧠 AI insights", "📥 Report"])
    with tabs[0]:
        _explain(a)
    with tabs[1]:
        _gaps(a)
    with tabs[2]:
        _action_plan(a, k)
    with tabs[3]:
        _role_fit(a, k)
    with tabs[4]:
        _what_if(a, k)
    with tabs[5]:
        _insights(a, k)
    with tabs[6]:
        _report(a, k)


# --------------------------------------------------------------------------- #
def _explain(a: Assessment) -> None:
    rows = [
        {
            "Component": c.name,
            "Weight": c.weight,
            "Achieved %": round(c.fraction * 100, 1),
            "Points": round(c.points, 2),
            "Lost": round(c.lost, 2),
            "How it was calculated": c.detail,
        }
        for c in a.result.components
    ]
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        column_config={
            "Achieved %": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f%%"),
        },
    )
    st.caption(
        f"Formula: Skills 35 + Projects 20 + Academics 15 + Soft skills 15 + Experience 10 + Certifications 5 = 100. "
        f"Levels: Ready ≥ {cfg.READY_THRESHOLD:.0f}, Almost ready ≥ {cfg.ALMOST_THRESHOLD:.0f}, otherwise Needs work."
    )


def _gaps(a: Assessment) -> None:
    r = a.result
    c1, c2 = st.columns(2)
    with c1:
        st.progress(r.skills_match_pct / 100, text=f"Required skills covered: {r.skills_match_pct:.0f}%")
        show_chips("✅ Required skills you have", r.matched_required, "good", "None yet. Start with the action plan.")
        show_chips("❌ Required skills missing", r.missing_required, "bad", "No required gaps. Excellent!")
    with c2:
        n_pref = len(r.matched_preferred) + len(r.missing_preferred)
        pref_pct = 100 * len(r.matched_preferred) / n_pref if n_pref else 0
        st.progress(pref_pct / 100, text=f"Nice-to-have skills covered: {pref_pct:.0f}%")
        show_chips("✅ Preferred skills you have", r.matched_preferred, "good", "None yet.")
        show_chips("➕ Preferred skills to stand out", r.missing_preferred, "warn", "You cover all of them!")
    relevant = set(r.matched_required) | set(r.matched_preferred)
    extra = [s for s in normalize_skills(a.profile.skills) if s not in relevant]
    if extra:
        show_chips("Other skills on your profile (not scored for this role)", extra, "neutral")


def _action_plan(a: Assessment, k: str) -> None:
    if not a.actions:
        st.success("No gaps found. Keep polishing your portfolio and practising interviews. 🎉")
        return
    hours = st.slider("Hours you can invest per week", 3, 30, 10, key=f"{k}_hours")
    timeline = build_timeline(a.actions, hours)
    if timeline:
        st.markdown("**Suggested timeline** (highest impact and quickest wins first)")
        st.dataframe(pd.DataFrame(timeline), hide_index=True, width="stretch")
        st.caption(f"Completing the top {min(5, len(a.actions))} actions could lift you from {a.result.total:.1f} to about {a.potential_score:.1f}.")
    st.markdown("**Step-by-step actions**")
    for idx, act in enumerate(a.actions, 1):
        label = f"{PRIORITY_ICONS.get(act.priority, '')} {idx}. {act.title}  |  +{act.impact_points:.1f} pts  |  ~{act.effort_hours} h"
        with st.expander(label, expanded=idx <= 2):
            for n, step in enumerate(act.steps, 1):
                st.markdown(f"{n}. {step}")
            if act.project_idea:
                st.info(f"**Mini-project:** {act.project_idea}")


def _role_fit(a: Assessment, k: str) -> None:
    st.plotly_chart(charts.role_fit_chart(a.role_scores, a.role), width="stretch", key=f"{k}_rolefit")
    best = max(a.role_scores, key=a.role_scores.get)  # type: ignore[arg-type]
    if best == a.role:
        st.success(f"**{a.role}** is already your best-fit role.")
    else:
        st.info(f"Your profile currently fits **{best}** ({a.role_scores[best]:.1f}) better than **{a.role}** ({a.role_scores[a.role]:.1f}).")


def _what_if(a: Assessment, k: str) -> None:
    st.caption("Change the inputs to see how the score reacts. This does not modify the stored student.")
    p = a.profile
    owned = set(normalize_skills(p.skills))
    options = [s for s in get_role(a.role).all_skills if s not in owned]
    c1, c2 = st.columns(2)
    with c1:
        learn = st.multiselect("Skills I will learn", options, key=f"{k}_wi_skills")
        extra_projects = st.slider("Additional projects", 0, 4, 0, key=f"{k}_wi_projects")
        extra_interns = st.slider("Additional internships", 0, 2, 0, key=f"{k}_wi_interns")
    with c2:
        extra_certs = st.slider("Additional certifications", 0, 3, 0, key=f"{k}_wi_certs")
        comm = st.slider("Communication score", 0, 100, int(round(p.communication_score)), key=f"{k}_wi_comm")
        apt = st.slider("Aptitude score", 0, 100, int(round(p.aptitude_score)), key=f"{k}_wi_apt")
    sim = replace(
        p,
        skills=tuple(p.skills) + tuple(learn),
        projects=p.projects + extra_projects,
        internships=p.internships + extra_interns,
        certifications=p.certifications + extra_certs,
        communication_score=comm,
        aptitude_score=apt,
    )
    new = score_student(sim, a.role)
    s1, s2 = st.columns(2)
    s1.metric("Simulated score", f"{new.total:.1f}", f"{new.total - a.result.total:+.1f} vs now")
    s2.metric("Simulated level", new.level, "level up!" if new.level != a.result.level and new.total > a.result.total else None)


def _insights(a: Assessment, k: str) -> None:
    for line in a.insights:
        st.markdown(f"- {line}")
    st.divider()
    key = f"{k}_coach"
    if st.button("✨ Generate AI coaching summary", key=f"{k}_coach_btn"):
        with st.spinner("Mentor is thinking..."):
            st.session_state[key] = ask_mentor(COACH_PROMPT, a, use_llm=st.session_state.get("use_llm", True))
    reply = st.session_state.get(key)
    if reply:
        st.markdown(reply.text)
        st.caption(f"Source: {'Ollama (' + cfg.OLLAMA_MODEL + ')' if reply.source == 'ollama' else 'rule-based mentor'}. {reply.note}")


def _report(a: Assessment, k: str) -> None:
    fname = safe_filename(a.profile.name)
    md = build_markdown_report(a)
    c1, c2 = st.columns(2)
    c1.download_button(
        "⬇️ Download Markdown report",
        data=md.encode("utf-8"),
        file_name=f"readiness_{fname}.md",
        mime="text/markdown",
        key=f"{k}_md",
        width="stretch",
    )
    pdf_key = f"{k}_pdf"
    if c2.button("📄 Prepare PDF report", key=f"{k}_pdf_btn", width="stretch"):
        try:
            st.session_state[pdf_key] = build_pdf_report(a)
        except ReportError as exc:
            st.error(str(exc))
    if st.session_state.get(pdf_key):
        c2.download_button(
            "⬇️ Download PDF report",
            data=st.session_state[pdf_key],
            file_name=f"readiness_{fname}.pdf",
            mime="application/pdf",
            key=f"{k}_pdf_dl",
            width="stretch",
        )
    with st.expander("Preview Markdown"):
        st.markdown(md)
