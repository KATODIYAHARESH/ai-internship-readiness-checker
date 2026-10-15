"""AI mentor tab: Ollama chat grounded in the student's score, with rule-based fallback."""

from __future__ import annotations

import streamlit as st

from .. import config as cfg
from ..llm import OllamaStatus, ask_mentor
from ..models import Assessment

SUGGESTIONS = [
    "Why is my score low?",
    "What should I learn first?",
    "Which role fits me best?",
    "How do I learn SQL?",
    "Give me a 4-week plan",
]

SOURCE_LABELS = {"student": "Student view", "resume": "Resume analysis"}


def _queue(question: str) -> None:
    st.session_state["pending_question"] = question


def _clear() -> None:
    st.session_state["chat_history"] = []


def render(status: OllamaStatus) -> None:
    """Render the mentor chat."""
    st.subheader("🤖 AI mentor")
    store: dict[str, Assessment] = st.session_state.get("assessments", {})
    if not store:
        st.info("Open the **Student** tab (or analyse a resume) first. The mentor needs a score and skill gaps as context.")
        return

    keys = list(store)
    key = keys[0]
    if len(keys) > 1:
        key = st.radio("Talk about", keys, format_func=lambda k: SOURCE_LABELS.get(k, k), horizontal=True, key="chat_source")
    a = store.get(key, store[keys[0]])

    use_llm = st.session_state.get("use_llm", True)
    if use_llm and status.usable:
        st.success(f"🟢 Ollama online: answers come from **{status.model}**, grounded in the score below.")
    elif use_llm:
        st.warning(f"🟠 {status.detail}. Using the built-in **rule-based mentor** (still personalised to the score).")
    else:
        st.info("Rule-based mode selected in the sidebar.")

    st.caption(
        f"Context: **{a.profile.name}** → **{a.role}**, score **{a.result.total:.1f}** ({a.result.level}); "
        f"missing: {', '.join(a.result.missing_required[:5]) or 'nothing'}"
    )

    ctx = (key, a.profile.name, a.role, a.result.total)
    if st.session_state.get("chat_ctx") != ctx:
        st.session_state["chat_ctx"] = ctx
        st.session_state["chat_history"] = []
    history: list[dict[str, str]] = st.session_state.setdefault("chat_history", [])

    cols = st.columns(len(SUGGESTIONS) + 1)
    for col, text in zip(cols, SUGGESTIONS):
        col.button(text, key=f"sugg_{text}", on_click=_queue, args=(text,), width="stretch")
    cols[-1].button("🗑️ Clear", key="chat_clear", on_click=_clear, width="stretch")

    box = st.container()
    typed = st.chat_input("Ask your mentor about your score, gaps or next steps...", key="mentor_input")
    question = st.session_state.pop("pending_question", None) or typed

    if question and question.strip():
        with st.spinner("Mentor is thinking..."):
            reply = ask_mentor(question, a, history=history, use_llm=use_llm, host=status.host, model=status.model)
        history.append({"role": "user", "content": question.strip()})
        history.append({"role": "assistant", "content": reply.text, "source": reply.source, "note": reply.note})

    with box:
        if not history:
            st.markdown(
                "_Try a suggestion above or type a question. Example: **'How do I learn Docker?'** or **'Am I ready to apply?'**_"
            )
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant":
                    label = f"🧠 Ollama · {cfg.OLLAMA_MODEL}" if msg.get("source") == "ollama" else "📋 Rule-based mentor"
                    st.caption(label + (f" · {msg['note']}" if msg.get("note") else ""))
