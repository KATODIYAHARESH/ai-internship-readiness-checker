"""Semantic matching of a resume against sample job descriptions.

Backends
--------
``tfidf``   (default) scikit-learn TF-IDF + cosine similarity. Fully offline.
``chroma``  ChromaDB vector store fed by Ollama embeddings (``nomic-embed-text``).
            Requires ``pip install chromadb`` and a running Ollama.
``auto``    try ``chroma`` and silently fall back to ``tfidf``.

Chroma's own default embedder downloads a model from the internet, so we compute
embeddings ourselves via Ollama and hand them to Chroma. Any failure falls back
to TF-IDF so the feature never crashes the app.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import requests

from . import config as cfg
from .catalog import job_descriptions
from .models import JobDescription, JobMatch

logger = logging.getLogger(__name__)

MIN_RESUME_CHARS = 20


# --------------------------------------------------------------------------- #
# TF-IDF backend
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _tfidf_index():
    """Fit the TF-IDF vectoriser once on the job-description corpus."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    jobs = job_descriptions()
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
        token_pattern=r"(?u)\b[\w+#.]{2,}\b",
    )
    matrix = vectorizer.fit_transform([f"{j.title}. {j.text}" for j in jobs])
    return vectorizer, matrix


def _rank_tfidf(resume_text: str) -> list[float]:
    from sklearn.metrics.pairwise import cosine_similarity

    vectorizer, matrix = _tfidf_index()
    query = vectorizer.transform([resume_text])
    return [float(x) for x in cosine_similarity(query, matrix)[0]]


# --------------------------------------------------------------------------- #
# Chroma + Ollama embeddings backend (optional)
# --------------------------------------------------------------------------- #
def _embed(text: str) -> list[float]:
    """Embed ``text`` with Ollama. Raises on any failure."""
    resp = requests.post(
        f"{cfg.OLLAMA_HOST}/api/embeddings",
        json={"model": cfg.OLLAMA_EMBED_MODEL, "prompt": text},
        timeout=cfg.OLLAMA_TIMEOUT,
    )
    resp.raise_for_status()
    vector = resp.json()["embedding"]
    if not vector:
        raise ValueError("Ollama returned an empty embedding")
    return vector


def _rank_chroma(resume_text: str) -> list[float]:
    """Cosine similarity through ChromaDB (in-memory). Raises if unavailable."""
    import chromadb  # optional dependency

    jobs = job_descriptions()
    client = chromadb.EphemeralClient()
    name = "job_descriptions"
    try:
        client.delete_collection(name)
    except Exception:  # noqa: BLE001 - collection may not exist
        pass
    collection = client.create_collection(name=name, metadata={"hnsw:space": "cosine"})
    collection.add(
        ids=[j.id for j in jobs],
        documents=[j.text for j in jobs],
        embeddings=[_embed(f"{j.title}. {j.text}") for j in jobs],
    )
    res = collection.query(query_embeddings=[_embed(resume_text[:4000])], n_results=len(jobs))
    sims = {jid: 1.0 - float(dist) for jid, dist in zip(res["ids"][0], res["distances"][0])}
    return [sims.get(j.id, 0.0) for j in jobs]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def match_jobs(resume_text: str, backend: str | None = None, top_k: int = 6) -> list[JobMatch]:
    """Rank sample job descriptions by semantic similarity to ``resume_text``.

    Args:
        resume_text: Plain resume text. Empty/very short input returns ``[]``.
        backend: ``tfidf`` | ``chroma`` | ``auto`` (defaults to ``SEMANTIC_BACKEND``).
        top_k: Number of matches to return.

    Returns:
        Matches sorted by descending similarity, scaled to 0-100.
    """
    if not resume_text or len(resume_text.strip()) < MIN_RESUME_CHARS:
        return []
    chosen = (backend or cfg.SEMANTIC_BACKEND).lower()
    jobs: tuple[JobDescription, ...] = job_descriptions()
    if not jobs:
        return []

    sims: list[float] | None = None
    used = "tfidf"
    if chosen in ("chroma", "auto"):
        try:
            sims = _rank_chroma(resume_text)
            used = "chroma + ollama embeddings"
        except Exception as exc:  # noqa: BLE001 - optional path must never crash the app
            logger.info("Chroma backend unavailable (%s); using TF-IDF", exc)
    if sims is None:
        try:
            sims = _rank_tfidf(resume_text)
        except ImportError:
            logger.warning("scikit-learn missing; semantic matching disabled")
            return []

    matches = [JobMatch(job=j, similarity=round(max(0.0, s) * 100, 1), backend=used) for j, s in zip(jobs, sims)]
    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches[:top_k]
