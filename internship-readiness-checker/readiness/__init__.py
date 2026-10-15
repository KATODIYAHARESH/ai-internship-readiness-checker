"""AI Internship Readiness Checker.

Package layout
--------------
config           environment-driven settings and scoring constants
models           typed dataclasses shared across layers
catalog          roles / skills / job descriptions loaded from ``data/catalog.json``
database         SQLite schema + data access (data layer)
seed             synthetic student generator (80 students by default)
scoring          pure, explainable 0-100 readiness score (scoring layer)
recommendations  skill-gap analysis, action plan, rule-based insights
resume           PDF/text parsing and skill extraction
semantic         resume <-> job-description matching (TF-IDF, optional ChromaDB)
llm              Ollama mentor with rule-based fallback (llm layer)
analytics        campus-wide aggregations for the placement dashboard
reports          Markdown / PDF report generation
service          orchestration helper that builds a full ``Assessment``
cache            Streamlit ``st.cache_data`` wrappers
ui/              Streamlit tabs and components (ui layer)
"""

__version__ = "1.0.0"
