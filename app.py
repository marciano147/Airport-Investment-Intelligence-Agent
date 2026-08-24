"""Streamlit chat interface."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

import streamlit as st

from agent import get_agent, response_content
from chat_store import (
    export_messages_json,
    init_store,
    list_conversations,
    load_messages,
    save_message,
)
from voice_utils import transcribe_audio, transcription_succeeded


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

st.set_page_config(
    page_title="Airport Investment Intelligence Agent",
    page_icon="✈️",
    layout="wide",
)
st.title("Airport Investment Intelligence Agent")
st.caption("Identify promising US airports for terminal and capacity modernization. Powered by Groq.")

init_store()

# Streamlit reruns the whole file after each interaction. These session values
# preserve chat messages, selected thread, debug output, and voice-recorder state
# across reruns.
if "messages" not in st.session_state:
    st.session_state.messages = []
if "last_response" not in st.session_state:
    st.session_state.last_response = None
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"airport-agent-{uuid.uuid4()}"
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "replay_next" not in st.session_state:
    st.session_state.replay_next = False
if "voice_input_version" not in st.session_state:
    st.session_state.voice_input_version = 0
if "voice_status" not in st.session_state:
    st.session_state.voice_status = None
if "voice_reset_after_response" not in st.session_state:
    st.session_state.voice_reset_after_response = False


def _start_new_conversation() -> None:
    """Reset UI and memory handles for a fresh analyst conversation."""
    st.session_state.thread_id = f"airport-agent-{uuid.uuid4()}"
    st.session_state.messages = []
    st.session_state.last_response = None
    st.session_state.last_audio_hash = None
    st.session_state.pending_prompt = None
    st.session_state.replay_next = False
    st.session_state.voice_input_version += 1
    st.session_state.voice_status = None
    st.session_state.voice_reset_after_response = False


def _queue_user_message(content: str) -> None:
    """Defer user input until the main chat-rendering section can append it."""
    st.session_state.pending_prompt = content


def _append_and_save(role: str, content: str) -> None:
    """Append a visible chat message and persist it to local SQLite history."""
    st.session_state.messages.append({"role": role, "content": content})
    save_message(st.session_state.thread_id, role, content)


def _load_conversation(thread_id: str) -> None:
    """Restore a saved sidebar conversation and replay context on next turn."""
    st.session_state.thread_id = thread_id
    st.session_state.messages = load_messages(thread_id)
    st.session_state.last_response = None
    st.session_state.last_audio_hash = None
    st.session_state.pending_prompt = None
    st.session_state.replay_next = True
    st.session_state.voice_input_version += 1
    st.session_state.voice_status = None
    st.session_state.voice_reset_after_response = False


def _render_voice_input() -> None:
    """Render sidebar voice recording and submit transcript as normal chat text."""
    st.subheader("Voice Input")
    voice_status_slot = st.empty()
    if st.session_state.voice_status:
        status_kind, status_message = st.session_state.voice_status
        if status_kind == "success":
            voice_status_slot.success(status_message)
        else:
            voice_status_slot.error(status_message)

    with st.form("voice_input_form", clear_on_submit=True):
        audio_data = st.audio_input(
            "Record a voice question",
            key=f"voice_input_{st.session_state.voice_input_version}",
        )
        send_voice = st.form_submit_button("Send Voice", use_container_width=True)

    if not send_voice:
        return

    if audio_data is None:
        message = "Record a voice question before sending."
        st.session_state.voice_status = ("error", message)
        voice_status_slot.error(message)
        return

    audio_bytes = audio_data.getvalue()
    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
    if audio_hash == st.session_state.last_audio_hash:
        return

    st.session_state.last_audio_hash = audio_hash
    with st.spinner("Transcribing with Groq Whisper..."):
        transcript = transcribe_audio(audio_bytes)

    if transcription_succeeded(transcript):
        # Reset the recorder only after the assistant response is saved. Resetting
        # during recorder completion can produce Streamlit's transient audio error.
        st.session_state.voice_input_version += 1
        st.session_state.voice_status = ("success", f'Heard: "{transcript}"')
        st.session_state.voice_reset_after_response = True
        voice_status_slot.success(st.session_state.voice_status[1])
        _queue_user_message(transcript)
        return

    message = transcript or "Transcription failed. Try recording again."
    st.session_state.voice_status = ("error", message)
    voice_status_slot.error(message)


with st.sidebar:
    # Sidebar order is intentional: controls and voice first, then history,
    # examples, and debugging.
    st.header("Controls")
    if st.button("New Conversation", use_container_width=True):
        _start_new_conversation()
        st.rerun()

    st.divider()
    _render_voice_input()

    conversations = list_conversations()
    if conversations:
        st.divider()
        st.subheader("Chat History")
        for conversation in conversations:
            is_current = conversation["thread_id"] == st.session_state.thread_id
            label = conversation["title"]
            if is_current:
                label = f"{label} (current)"
            if st.button(
                label,
                use_container_width=True,
                key=f"history-{conversation['thread_id']}",
            ):
                _load_conversation(conversation["thread_id"])
                st.rerun()

        st.download_button(
            "Export Current Chat",
            data=export_messages_json(st.session_state.thread_id),
            file_name=f"{st.session_state.thread_id}.json",
            mime="application/json",
            use_container_width=True,
        )

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
            _queue_user_message(example)
            st.rerun()

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
    _queue_user_message(prompt)

if st.session_state.pending_prompt:
    # Text input, example buttons, and voice transcripts all converge here so
    # every user turn uses the same persistence and agent invocation path.
    pending = st.session_state.pending_prompt
    st.session_state.pending_prompt = None
    _append_and_save("user", pending)
    st.chat_message("user").write(pending)

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Analyzing airport data..."):
            try:
                latest_user_message = st.session_state.messages[-1]
                if st.session_state.replay_next:
                    # Restored SQLite conversations do not automatically exist
                    # inside LangGraph's in-memory checkpointer after a restart,
                    # so replay saved messages once before the next answer.
                    input_messages = [
                        {"role": message["role"], "content": message["content"]}
                        for message in st.session_state.messages
                    ]
                    st.session_state.replay_next = False
                else:
                    input_messages = [latest_user_message]
                agent = get_agent()
                response = agent.invoke(
                    {"messages": input_messages},
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
        _append_and_save("assistant", content)
        if st.session_state.voice_reset_after_response:
            st.session_state.voice_reset_after_response = False
            st.rerun()
