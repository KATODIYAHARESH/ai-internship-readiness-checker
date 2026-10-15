"""Streamlit ``st.cache_data`` wrappers around the data / scoring / llm layers.

Business logic stays Streamlit-free; this module is the only place where
caching decisions live. Call :func:`clear_all` after reseeding the database.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import analytics, database, llm, semantic
from .models import JobMatch


@st.cache_data(show_spinner=False)
def load_students(db_path: str) -> pd.DataFrame:
    """Load students (auto-seeding the DB on first run)."""
    database.ensure_database(db_path)
    return database.fetch_students_df(db_path)


@st.cache_data(show_spinner=False)
def score_campus(db_path: str, role_override: str | None = None) -> pd.DataFrame:
    """Score every student, optionally against one role for all."""
    return analytics.score_dataframe(load_students(db_path), role_override)


@st.cache_data(show_spinner=False)
def match_jobs(resume_text: str, backend: str) -> list[JobMatch]:
    """Semantic resume <-> job-description ranking."""
    return semantic.match_jobs(resume_text, backend)


@st.cache_data(ttl=20, show_spinner=False)
def ollama_status(host: str, model: str) -> llm.OllamaStatus:
    """Probe Ollama at most once every 20 seconds."""
    return llm.check_ollama(host, model)


def clear_all() -> None:
    """Invalidate every cached value (used after regenerating the dataset)."""
    st.cache_data.clear()
