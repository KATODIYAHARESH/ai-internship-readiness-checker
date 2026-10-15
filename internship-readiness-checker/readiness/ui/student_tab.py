"""Student tab: pick a student and role, then show the full assessment."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ..catalog import role_names
from ..models import StudentProfile
from ..service import assess
from .assessment_view import render_assessment
from .components import set_active_assessment


def render(students: pd.DataFrame) -> None:
    """Render the student readiness view."""
    st.subheader("🎓 Student readiness view")
    if students.empty:
        st.warning("No students found. Run `python seed_db.py` or use **Dataset tools** in the sidebar.")
        return

    labels = {int(r["id"]): f"{r['name']}  ·  {r['major']}" for _, r in students.iterrows()}
    ids = list(labels)
    c1, c2 = st.columns([2, 1])
    sid = c1.selectbox("Student (type to search)", ids, format_func=labels.get, key="student_select")
    row = students.loc[students["id"] == sid].iloc[0].to_dict()
    profile = StudentProfile.from_mapping(row)

    roles = role_names()
    default_idx = roles.index(profile.target_role) if profile.target_role in roles else 0
    role = c2.selectbox("Target role", roles, index=default_idx, key=f"student_role_{sid}")

    with st.expander("Student profile data", expanded=False):
        p = profile
        st.write(
            f"**Major:** {p.major} | **Year:** {row.get('year', '-')} | **CGPA:** {p.cgpa:.2f} | "
            f"**Projects:** {p.projects} | **Internships:** {p.internships} | **Certifications:** {p.certifications} | "
            f"**Communication:** {p.communication_score:.0f} | **Aptitude:** {p.aptitude_score:.0f}"
        )
        st.write("**Skills:** " + (", ".join(p.skills) or "none listed"))

    assessment = assess(profile, role, source="student")
    set_active_assessment("student", assessment)
    render_assessment(assessment, "student")
