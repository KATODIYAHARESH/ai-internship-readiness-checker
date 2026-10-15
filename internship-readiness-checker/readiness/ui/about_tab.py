"""About tab: how the score works, role requirements, architecture."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import config as cfg
from ..catalog import roles

ARCHITECTURE = """
Streamlit UI  (app.py + readiness/ui/*)
   |  student tab | resume tab | placement dashboard | AI mentor
   v
service.assess()  ->  scoring  ->  recommendations  ->  reports
   |                                   |
   |                                   +--> llm.py  (Ollama llama3.2  --fallback-->  rule-based mentor)
   v
cache.py (st.cache_data) -> analytics.py -> database.py -> SQLite (data/readiness.db)
                                                  ^
                          seed.py / seed_db.py ---+       catalog.json (roles, skills, playbooks, JDs)
resume.py (PDF/text -> skills) -> semantic.py (TF-IDF | ChromaDB + Ollama embeddings)
"""


def render() -> None:
    """Render the explanatory tab."""
    st.subheader("ℹ️ How the readiness score works")
    weights = pd.DataFrame(
        [
            {"Component": cfg.W_SKILLS, "Weight": 35, "Rule": "85% required-skill coverage + 15% preferred-skill coverage for the chosen role"},
            {"Component": cfg.W_PROJECTS, "Weight": 20, "Rule": f"projects / {cfg.PROJECTS_CAP}, capped at 1"},
            {"Component": cfg.W_ACADEMICS, "Weight": 15, "Rule": f"60% CGPA (5.0 -> 0, 10 -> 1) + 40% aptitude score"},
            {"Component": cfg.W_SOFT, "Weight": 15, "Rule": "communication score / 100"},
            {"Component": cfg.W_EXPERIENCE, "Weight": 10, "Rule": f"internships / {cfg.INTERNSHIPS_CAP}, capped at 1"},
            {"Component": cfg.W_CERTS, "Weight": 5, "Rule": f"certifications / {cfg.CERTIFICATIONS_CAP}, capped at 1"},
        ]
    )
    st.dataframe(weights, hide_index=True, width="stretch")
    st.markdown(
        f"**Levels:** 🟢 Ready ≥ {cfg.READY_THRESHOLD:.0f} · 🟡 Almost ready {cfg.ALMOST_THRESHOLD:.0f}-74 · 🔴 Needs work < {cfg.ALMOST_THRESHOLD:.0f}"
    )

    st.markdown("#### Target roles and required skills")
    role_rows = [
        {"Role": r.name, "Required": ", ".join(r.required), "Preferred": ", ".join(r.preferred)} for r in roles().values()
    ]
    st.dataframe(pd.DataFrame(role_rows), hide_index=True, width="stretch")

    st.markdown("#### Architecture")
    st.code(ARCHITECTURE, language="text")
    st.caption("All data in this prototype is synthetic. Scores are guidance for students, not hiring decisions.")
