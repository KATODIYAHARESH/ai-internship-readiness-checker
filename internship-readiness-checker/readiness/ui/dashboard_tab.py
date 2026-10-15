"""Placement-cell dashboard: campus KPIs, department view, skill gaps, at-risk list."""

from __future__ import annotations

import streamlit as st

from .. import analytics, cache
from .. import config as cfg
from ..catalog import role_names
from . import charts


def render(db_path: str) -> None:
    """Render the placement dashboard."""
    st.subheader("🏫 Placement-cell dashboard")
    students = cache.load_students(db_path)
    if students.empty:
        st.warning("The database is empty. Run `python seed_db.py` or use **Dataset tools** in the sidebar.")
        return

    with st.container(border=True):
        f1, f2, f3 = st.columns(3)
        mode = f1.radio("Evaluate students against", ["Their own target role", "One role for everyone"], key="dash_mode")
        role_override = f1.selectbox("Role", role_names(), key="dash_role") if mode == "One role for everyone" else None
        departments = sorted(students["major"].unique())
        chosen = f2.multiselect("Departments", departments, default=departments, key="dash_depts")
        threshold = f3.slider("At-risk threshold (score below)", 30, 75, int(cfg.ALMOST_THRESHOLD), key="dash_threshold")

    scored_all = cache.score_campus(db_path, role_override)
    scored = scored_all[scored_all["major"].isin(chosen)]
    if scored.empty:
        st.info("No students match the selected departments. Pick at least one department.")
        return

    kpis = analytics.campus_kpis(scored)
    at_risk = analytics.at_risk_students(scored, threshold)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Students", kpis["students"])
    k2.metric("Average score", f"{kpis['avg_score']:.1f}", f"median {kpis['median_score']:.1f}", delta_color="off")
    k3.metric("% Ready (75+)", f"{kpis['pct_ready']:.1f}%")
    k4.metric("% Almost ready", f"{kpis['pct_almost']:.1f}%")
    k5.metric(f"At risk (< {threshold})", len(at_risk), f"{100 * len(at_risk) / kpis['students']:.0f}% of cohort", delta_color="off")

    dist = analytics.level_distribution(scored)
    depts = analytics.by_department(scored)
    gaps = analytics.top_skill_gaps(scored, 10)
    comps = analytics.component_averages(scored)

    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.level_donut(dist), width="stretch", key="dash_donut")
    c2.plotly_chart(charts.department_chart(depts), width="stretch", key="dash_dept")

    c3, c4 = st.columns(2)
    if gaps.empty:
        c3.success("No required-skill gaps in this cohort.")
    else:
        c3.plotly_chart(charts.skill_gap_chart(gaps), width="stretch", key="dash_gaps")
    c4.plotly_chart(charts.component_chart(comps), width="stretch", key="dash_components")

    with st.container(border=True):
        st.markdown("#### 💡 Campus insights")
        for line in analytics.campus_insights(scored, gaps, depts):
            st.markdown(f"- {line}")

    st.markdown("#### 🚨 At-risk students")
    if at_risk.empty:
        st.success("Nobody is below the threshold. 🎉")
    else:
        st.dataframe(
            at_risk,
            hide_index=True,
            width="stretch",
            column_config={
                "name": "Student",
                "major": "Department",
                "evaluated_role": "Role",
                "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.1f"),
                "weakest_area": "Biggest loss",
                "top_missing_skills": "Top missing skills",
            },
        )

    d1, d2, d3 = st.columns([1, 1, 2])
    d1.download_button(
        "⬇️ At-risk list (CSV)",
        data=analytics.to_csv_bytes(at_risk),
        file_name="at_risk_students.csv",
        mime="text/csv",
        disabled=at_risk.empty,
        key="dl_at_risk",
    )
    d2.download_button(
        "⬇️ All scores (CSV)",
        data=analytics.to_csv_bytes(scored),
        file_name="campus_readiness.csv",
        mime="text/csv",
        key="dl_all",
    )

    c5, c6 = st.columns(2)
    c5.plotly_chart(charts.score_scatter(scored), width="stretch", key="dash_scatter")
    with c6:
        st.markdown("#### Department table")
        st.dataframe(
            depts,
            hide_index=True,
            width="stretch",
            column_config={
                "major": "Department",
                "students": "Students",
                "avg_score": st.column_config.NumberColumn("Avg score", format="%.1f"),
                "pct_ready": st.column_config.NumberColumn("% Ready", format="%.1f"),
                "pct_at_risk": st.column_config.NumberColumn("% At risk", format="%.1f"),
            },
        )
    with st.expander("Full scored dataset"):
        st.dataframe(scored.drop(columns=["missing_required"]), hide_index=True, width="stretch")
