"""Streamlit chat interface."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

import streamlit as st

from agent import get_agent, response_content
from voice_utils import transcribe_audio


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

st.set_page_config(
    page_title="Airport Investment Intelligence Agent",
    page_icon="✈️",
    layout="wide",
)
st.title("Airport Investment Intelligence Agent")
st.caption("Identify promising US airports for terminal and capacity modernization. Powered by Groq.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_response" not in st.session_state:
    st.session_state.last_response = None
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"airport-agent-{uuid.uuid4()}"
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None

with st.sidebar:
    st.header("Controls")
    if st.button("New Conversation", use_container_width=True):
        st.session_state.thread_id = f"airport-agent-{uuid.uuid4()}"
        st.session_state.messages = []
        st.session_state.last_response = None
        st.session_state.last_audio_hash = None
        st.rerun()

    st.divider()
    st.subheader("Example Questions")
    examples = [
        "Which airports in New England are strong candidates for terminal expansion?",
        "Rank the top 5 US airports for terminal expansion.",
        "Rank California airports for capacity investment potential.",
        "Compare LAX and SNA congestion levels.",
        "What is the percentage of long-haul flights out of Anchorage airport?",
        "What is the unmet flight demand in SFO airport and why?",
        "Compare SFO and LAX on growth and congestion.",
    ]
    for example in examples:
        if st.button(example, use_container_width=True, key=f"example-{example}"):
            st.session_state.messages.append({"role": "user", "content": example})
            st.rerun()

    st.divider()
    st.subheader("Voice Input (Bonus)")
    audio_data = st.audio_input("Record your question")
    if audio_data is not None:
        audio_bytes = audio_data.read()
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()
        if audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("Transcribing with Groq Whisper..."):
                transcript = transcribe_audio(audio_bytes)
            if transcript and not transcript.startswith("[Transcription error:"):
                st.caption(f'Heard: "{transcript}"')
                st.session_state.messages.append({"role": "user", "content": transcript})
                st.rerun()
            else:
                st.error(transcript or "Transcription failed.")

    st.divider()
    st.subheader("Debug / Monitoring")
    show_raw = st.checkbox("Show debug info")
    show_trace = st.checkbox("Show LangSmith setup")
    st.caption("Enable LangSmith for full traces.")
    if show_trace:
        st.code(
            "export LANGSMITH_TRACING=true\n"
            "export LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com\n"
            "export LANGSMITH_API_KEY=\n"
            "export LANGSMITH_PROJECT=airport-agent",
            language="bash",
        )
    if show_raw and st.session_state.last_response:
        st.caption(f"Thread: {st.session_state.thread_id}")
        st.json(st.session_state.last_response)


for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])


def _content_from_response(response: dict[str, Any]) -> str:
    return response_content(response)


if prompt := st.chat_input("Ask about airport investment opportunities..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Analyzing airport data..."):
            try:
                latest_user_message = st.session_state.messages[-1]
                agent = get_agent()
                response = agent.invoke(
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
                if show_raw:
                    with st.expander("Raw agent result"):
                        st.json(st.session_state.last_response)
            except Exception as exc:
                logging.exception("Agent invocation failed")
                content = f"Error: {exc}"
                st.session_state.last_response = {"error": str(exc)}

        st.markdown(content)
        st.session_state.messages.append({"role": "assistant", "content": content})
