"""Small reusable Streamlit helpers (CSS, chips, badges, error boundary)."""

from __future__ import annotations

import hashlib
import html
import logging
import re
from typing import Any, Callable, Iterable

import streamlit as st

from .. import config as cfg
from ..models import Assessment

logger = logging.getLogger(__name__)

LEVEL_COLORS = {
    cfg.LEVEL_READY: "#16a34a",
    cfg.LEVEL_ALMOST: "#d97706",
    cfg.LEVEL_NEEDS_WORK: "#dc2626",
}
LEVEL_ICONS = {cfg.LEVEL_READY: "🟢", cfg.LEVEL_ALMOST: "🟡", cfg.LEVEL_NEEDS_WORK: "🔴"}
PRIORITY_ICONS = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}

_CHIP_STYLES = {
    "good": ("#dcfce7", "#166534"),
    "bad": ("#fee2e2", "#991b1b"),
    "warn": ("#fef3c7", "#92400e"),
    "neutral": ("#e2e8f0", "#1e293b"),
}

_CSS = """
<style>
.block-container {padding-top: 1.6rem; max-width: 1280px;}
.chip {display:inline-block; padding:2px 10px; margin:2px 4px 2px 0; border-radius:999px;
       font-size:0.82rem; font-weight:600; white-space:nowrap;}
.level-badge {display:inline-block; padding:4px 14px; border-radius:8px; color:white; font-weight:700;}
div[data-testid="stMetric"] {background: rgba(148,163,184,0.10); border-radius: 12px; padding: 10px 14px;}
</style>
"""


def inject_css() -> None:
    """Inject the app-wide CSS once per run."""
    st.markdown(_CSS, unsafe_allow_html=True)


def chips_html(items: Iterable[str], kind: str = "neutral") -> str:
    """Return HTML for coloured pills (content is HTML-escaped)."""
    bg, fg = _CHIP_STYLES.get(kind, _CHIP_STYLES["neutral"])
    return "".join(
        f'<span class="chip" style="background:{bg};color:{fg}">{html.escape(str(i))}</span>' for i in items
    )


def show_chips(label: str, items: Iterable[str], kind: str, empty: str = "None") -> None:
    """Render ``label`` followed by coloured chips (or ``empty`` text)."""
    items = list(items)
    st.markdown(f"**{label}**")
    if items:
        st.markdown(chips_html(items, kind), unsafe_allow_html=True)
    else:
        st.caption(empty)


def level_badge(level: str) -> str:
    """HTML badge coloured by readiness level."""
    color = LEVEL_COLORS.get(level, "#475569")
    return f'<span class="level-badge" style="background:{color}">{html.escape(level)}</span>'


def signature(a: Assessment) -> str:
    """Short stable id for an assessment (used to namespace widget keys)."""
    raw = f"{a.profile.name}|{a.profile.student_id}|{a.role}|{a.result.total}|{a.source}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]  # noqa: S324 - not security related


def safe_filename(name: str, default: str = "report") -> str:
    """Filesystem-safe slug."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name or "").strip("_")
    return slug or default


def set_active_assessment(key: str, assessment: Assessment) -> None:
    """Remember the latest assessment so the mentor tab can use it as context."""
    store: dict[str, Assessment] = st.session_state.setdefault("assessments", {})
    store[key] = assessment


def safe_render(label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    """Run a tab renderer; show a friendly error instead of crashing the app."""
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - UI error boundary
        logger.exception("Unhandled error in %s", label)
        st.error(f"Something went wrong in **{label}**: {exc}")
        st.caption("The rest of the app is unaffected. Check the terminal for the full traceback.")
