"""Central configuration.

Nothing secret lives in code. Every runtime option can be overridden with an
environment variable (see ``.env.example``).
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR: Path = Path(__file__).resolve().parent
PROJECT_DIR: Path = PACKAGE_DIR.parent
CATALOG_PATH: Path = PACKAGE_DIR / "data" / "catalog.json"


def _env_float(name: str, default: float) -> float:
    """Read a float from the environment, falling back to ``default``."""
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
DB_PATH: Path = Path(os.environ.get("READINESS_DB_PATH", PROJECT_DIR / "data" / "readiness.db"))
DEFAULT_STUDENT_COUNT: int = 80
DEFAULT_SEED: int = 42

# --------------------------------------------------------------------------- #
# Scoring model  (weights sum to 100)
# --------------------------------------------------------------------------- #
W_SKILLS = "Skills match"
W_PROJECTS = "Projects"
W_ACADEMICS = "Academics"
W_SOFT = "Soft skills"
W_EXPERIENCE = "Experience"
W_CERTS = "Certifications"

WEIGHTS: dict[str, float] = {
    W_SKILLS: 35.0,
    W_PROJECTS: 20.0,
    W_ACADEMICS: 15.0,
    W_SOFT: 15.0,
    W_EXPERIENCE: 10.0,
    W_CERTS: 5.0,
}

LEVEL_READY = "Ready"
LEVEL_ALMOST = "Almost ready"
LEVEL_NEEDS_WORK = "Needs work"
READY_THRESHOLD: float = 75.0  # score >= 75  -> Ready
ALMOST_THRESHOLD: float = 50.0  # 50 <= score < 75 -> Almost ready, below -> Needs work

CGPA_MAX: float = 10.0  # 10-point scale
CGPA_FLOOR: float = 5.0  # CGPA at/below the floor earns 0 of the CGPA share
CGPA_SHARE: float = 0.6  # academics = 60% CGPA + 40% aptitude
APTITUDE_SHARE: float = 0.4
REQUIRED_SKILL_SHARE: float = 0.85  # skills = 85% required coverage + 15% preferred

PROJECTS_CAP: int = 4  # 4+ projects earns full marks
INTERNSHIPS_CAP: int = 2  # 2+ internships earns full marks
CERTIFICATIONS_CAP: int = 3  # 3+ certifications earns full marks

# --------------------------------------------------------------------------- #
# LLM (Ollama) -- optional, everything degrades to rule-based answers
# --------------------------------------------------------------------------- #
OLLAMA_HOST: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "llama3.2")
OLLAMA_EMBED_MODEL: str = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT: float = _env_float("OLLAMA_TIMEOUT", 90.0)

# --------------------------------------------------------------------------- #
# Semantic matching: "tfidf" (offline default), "chroma" (needs chromadb + Ollama
# embeddings) or "auto" (try chroma, fall back to tfidf)
# --------------------------------------------------------------------------- #
SEMANTIC_BACKEND: str = os.environ.get("SEMANTIC_BACKEND", "tfidf").lower()
