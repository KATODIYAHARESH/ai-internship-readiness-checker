"""Resume analyzer tab: paste or upload a PDF, extract skills, score, match jobs."""

from __future__ import annotations

import hashlib

import streamlit as st

from .. import cache
from .. import config as cfg
from ..catalog import all_skill_names, role_names
from ..models import StudentProfile
from ..resume import SAMPLE_RESUME, ResumeParseError, analyze_resume, extract_text_from_pdf, guess_name
from ..service import assess
from .assessment_view import render_assessment
from .components import set_active_assessment, show_chips


def _load_sample() -> None:
    st.session_state["resume_text"] = SAMPLE_RESUME


def _read_input() -> str:
    """Return the resume text from the paste box or the uploaded PDF ('' if none)."""
    mode = st.radio("Resume source", ["Paste text", "Upload PDF"], horizontal=True, key="resume_mode")
    if mode == "Paste text":
        st.text_area(
            "Paste your resume text",
            height=280,
            key="resume_text",
            placeholder="Paste the full text of your resume here: education, skills, projects, experience, certifications...",
        )
        st.button("📋 Load a sample resume", on_click=_load_sample, key="resume_sample_btn")
        return st.session_state.get("resume_text", "") or ""

    upload = st.file_uploader("Upload a text-based PDF (max 10 MB)", type=["pdf"], key="resume_pdf")
    if upload is None:
        return ""
    try:
        text = extract_text_from_pdf(upload.getvalue())
    except ResumeParseError as exc:
        st.error(str(exc))
        return ""
    with st.expander("Extracted text"):
        st.text(text[:6000] + ("..." if len(text) > 6000 else ""))
    return text


def render() -> None:
    """Render the resume analyzer."""
    st.subheader("📄 Resume analyzer")
    st.caption("Skills are extracted offline with an alias dictionary; job matching uses TF-IDF (or ChromaDB + Ollama embeddings if enabled).")

    text = _read_input()
    if not text.strip():
        st.info("Paste resume text (or upload a PDF) to extract skills and get a role-specific readiness score.")
        return

    insights = analyze_resume(text)
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()[:8]  # noqa: S324 - widget key only

    st.divider()
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Detected skills")
        chosen = st.multiselect(
            "Add or remove skills before scoring",
            all_skill_names(),
            default=list(insights.skills),
            key=f"resume_skills_{digest}",
        )
        if not chosen:
            st.warning("No recognised skills found. Add them manually above, e.g. Python, SQL, Git.")
    with right:
        st.markdown("#### Resume health")
        st.metric("Words", insights.word_count)
        st.write("Sections found: " + (", ".join(s.title() for s in insights.sections) or "none"))
        for tip in insights.tips:
            st.markdown(f"- {tip}")

    st.markdown("#### Complete the profile")
    st.caption("Counts below are estimated from your resume; adjust anything that is wrong.")
    c1, c2, c3, c4 = st.columns(4)
    name = c1.text_input("Name", value=guess_name(text), key=f"resume_name_{digest}")
    role = c2.selectbox("Target role", role_names(), key=f"resume_role_{digest}")
    cgpa = c3.number_input("CGPA (/10)", 0.0, 10.0, float(insights.cgpa or 7.0), 0.1, key=f"resume_cgpa_{digest}")
    major = c4.text_input("Major", value="Computer Science", key=f"resume_major_{digest}")
    d1, d2, d3, d4, d5 = st.columns(5)
    projects = d1.number_input("Projects", 0, 20, int(insights.projects), key=f"resume_projects_{digest}")
    internships = d2.number_input("Internships", 0, 10, int(insights.internships), key=f"resume_interns_{digest}")
    certs = d3.number_input("Certifications", 0, 20, int(insights.certifications), key=f"resume_certs_{digest}")
    comm = d4.slider("Communication", 0, 100, 60, key=f"resume_comm_{digest}")
    apt = d5.slider("Aptitude", 0, 100, 60, key=f"resume_apt_{digest}")

    profile = StudentProfile(
        name=name.strip() or "Resume candidate",
        major=major.strip() or "Unknown",
        cgpa=cgpa,
        projects=int(projects),
        internships=int(internships),
        certifications=int(certs),
        communication_score=comm,
        aptitude_score=apt,
        skills=tuple(chosen),
        target_role=role,
    )
    assessment = assess(profile, role, source="resume")
    set_active_assessment("resume", assessment)

    st.divider()
    render_assessment(assessment, "resume")

    st.divider()
    st.markdown("#### 🔎 Semantic match to sample job descriptions")
    backends = ["tfidf", "auto", "chroma"]
    backend = st.selectbox(
        "Matching engine",
        backends,
        index=backends.index(cfg.SEMANTIC_BACKEND) if cfg.SEMANTIC_BACKEND in backends else 0,
        help="tfidf is fully offline. 'auto' tries ChromaDB with Ollama embeddings and falls back to tfidf.",
        key="semantic_backend",
    )
    matches = cache.match_jobs(text, backend)
    if not matches:
        st.info("Not enough text to compute semantic matches yet.")
        return
    st.caption(f"Engine used: {matches[0].backend}. Compare ranking order; absolute percentages are relative to the sample postings.")
    top = matches[0].similarity or 1.0
    for m in matches[:5]:
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"**{m.job.title}** at {m.job.company}  \n<small>{m.job.role}</small>", unsafe_allow_html=True)
        c1.progress(min(1.0, m.similarity / top), text=None)
        c2.metric("Similarity", f"{m.similarity:.1f}%")
    best_role = matches[0].job.role
    if best_role != role:
        st.info(f"Your resume language is closest to **{best_role}** postings, but you selected **{role}**.")
    show_chips("Skills the best-matching posting emphasises that you lack", _lacking(matches[0].job.text, chosen), "warn", "None")


def _lacking(job_text: str, owned: list[str]) -> list[str]:
    """Skills mentioned in a job description that the candidate does not list."""
    from ..resume import extract_skills

    have = set(owned)
    return [s for s in extract_skills(job_text) if s not in have]
