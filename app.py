"""Streamlit chat interface."""

from __future__ import annotations

import logging
import uuid
from typing import Any

import streamlit as st

from agent import get_agent


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

st.set_page_config(page_title="Airport Investment Intelligence Agent", page_icon="✈️")
st.title("Airport Investment Intelligence Agent")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_response" not in st.session_state:
    st.session_state.last_response = None
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"airport-agent-{uuid.uuid4()}"

with st.sidebar:
    st.subheader("Example Questions")
    examples = [
        "Rank the top 5 US airports for terminal expansion.",
        "Rank California airports for capacity investment potential.",
        "Compare LAX and SNA congestion levels.",
        "Estimate long-haul share at ANC.",
        "What assumptions should I know before using this ranking?",
    ]
    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": example})

    st.subheader("Debug / Monitoring")
    show_raw = st.checkbox("Show raw agent response")
    show_trace = st.checkbox("Show LangSmith setup")
    if show_trace:
        st.code(
            "export LANGSMITH_TRACING=true\n"
            "export LANGSMITH_API_KEY=\n"
            "export LANGSMITH_PROJECT=airport-agent",
            language="bash",
        )
    if show_raw and st.session_state.last_response:
        st.json(st.session_state.last_response)


for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])


def _content_from_response(response: dict[str, Any]) -> str:
    messages = response.get("messages", [])
    if not messages:
        return "No response returned."
    last = messages[-1]
    return getattr(last, "content", str(last))


if prompt := st.chat_input("Ask about airports..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Analyzing airport data..."):
            try:
                latest_user_message = st.session_state.messages[-1]
                response = get_agent().invoke(
                    {"messages": [latest_user_message]},
                    config={"configurable": {"thread_id": st.session_state.thread_id}},
                )
                st.session_state.last_response = {
                    "messages": [
                        getattr(msg, "content", str(msg))
                        for msg in response.get("messages", [])
                    ]
                }
                content = _content_from_response(response)
            except Exception as exc:
                logging.exception("Agent invocation failed")
                content = f"Agent failed: {exc}. Check API keys, cached data, and logs."
                st.session_state.last_response = {"error": str(exc)}

        st.write(content)
        st.session_state.messages.append({"role": "assistant", "content": content})
