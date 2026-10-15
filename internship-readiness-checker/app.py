"""AI Internship Readiness Checker: Streamlit entry point.

Run with::

    streamlit run app.py
"""

from __future__ import annotations

import logging
from contextlib import closing

import streamlit as st

from readiness import cache
from readiness import config as cfg
from readiness import database as db
from readiness.llm import OllamaStatus
from readiness.seed import generate_students
from readiness.ui import about_tab, chat_tab, dashboard_tab, resume_tab, student_tab
from readiness.ui.components import inject_css, safe_render

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="Internship Readiness Checker", page_icon="🎯", layout="wide")


def _reseed(count: int, seed: int, db_path: str) -> None:
    """Drop and regenerate the synthetic dataset, then clear all caches."""
    with closing(db.connect(db_path)) as conn:
        db.reset_schema(conn)
        db.insert_students(conn, generate_students(count, seed))
    cache.clear_all()


def _sidebar(n_students: int, status: OllamaStatus, db_path: str) -> None:
    with st.sidebar:
        st.title("🎯 Readiness Checker")
        st.caption("AI internship readiness for university students")
        st.metric("Students in database", n_students)
        st.caption(f"SQLite: `{db_path}`")
        st.divider()

        st.subheader("AI mentor engine")
        st.toggle("Use Ollama when available", value=True, key="use_llm")
        if status.usable:
            st.success(f"Ollama online · {status.model}")
        elif status.online:
            st.warning(status.detail)
        else:
            st.info("Ollama offline → rule-based mentor is active")
        if st.button("Re-check Ollama", key="recheck_ollama"):
            cache.ollama_status.clear()
            st.rerun()
        st.caption(f"Host `{status.host}` · set OLLAMA_HOST / OLLAMA_MODEL to change")

        st.divider()
        with st.expander("Dataset tools"):
            count = st.number_input("Students", 10, 500, cfg.DEFAULT_STUDENT_COUNT, step=10, key="seed_count")
            seed = st.number_input("Random seed", 0, 99999, cfg.DEFAULT_SEED, key="seed_value")
            if st.button("Regenerate synthetic data", key="reseed_btn"):
                try:
                    _reseed(int(count), int(seed), db_path)
                except Exception as exc:  # noqa: BLE001 - show, don't crash
                    st.error(f"Could not regenerate data: {exc}")
                else:
                    st.rerun()


def main() -> None:
    """Assemble the page."""
    inject_css()
    db_path = str(cfg.DB_PATH)
    try:
        students = cache.load_students(db_path)
    except Exception as exc:  # noqa: BLE001 - DB problems should be explained, not crash
        st.error(f"Could not open the student database at `{db_path}`: {exc}")
        st.stop()
        return
    status = cache.ollama_status(cfg.OLLAMA_HOST, cfg.OLLAMA_MODEL)
    _sidebar(len(students), status, db_path)

    st.title("AI Internship Readiness Checker")
    st.caption("Explainable, role-specific readiness scores · skill-gap action plans · resume analyzer · placement analytics · AI mentor")

    tabs = st.tabs(["🎓 Student", "📄 Resume Analyzer", "🏫 Placement Dashboard", "🤖 AI Mentor", "ℹ️ How it works"])
    with tabs[0]:
        safe_render("Student view", student_tab.render, students)
    with tabs[1]:
        safe_render("Resume analyzer", resume_tab.render)
    with tabs[2]:
        safe_render("Placement dashboard", dashboard_tab.render, db_path)
    with tabs[3]:
        safe_render("AI mentor", chat_tab.render, status)
    with tabs[4]:
        safe_render("How it works", about_tab.render)


main()
