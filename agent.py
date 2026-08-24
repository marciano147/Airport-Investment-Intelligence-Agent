"""LLM layer: question routing, tool selection, and response synthesis."""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from prompts import load_context
from tools import (
    compare_airports,
    get_airport_info,
    get_congestion,
    get_long_haul_estimate,
    get_passenger_metrics,
    rank_airports_for_expansion,
)


load_dotenv()

# LLM configuration lives here. The compute layer stays in `tools.py`,
# `data_loader.py`, and `scoring.py`, so the model routes questions but does not
# invent rankings or calculate scores itself.
MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
CHECKPOINTER = MemorySaver()

# Tools are registered once and reused by Streamlit, CLI smoke tests, and direct
# agent calls. Keep this list aligned with `context/TOOLS.md`.
AGENT_TOOLS = [
    get_airport_info,
    get_congestion,
    get_passenger_metrics,
    rank_airports_for_expansion,
    compare_airports,
    get_long_haul_estimate,
]
_AGENT: CompiledStateGraph | None = None


def build_agent() -> CompiledStateGraph:
    """Create the LangGraph agent after credentials are available."""
    llm = ChatGroq(model=MODEL, temperature=0, api_key=os.getenv("GROQ_API_KEY"))
    system_prompt = load_context()
    return create_react_agent(
        llm,
        tools=AGENT_TOOLS,
        prompt=system_prompt,
        checkpointer=CHECKPOINTER,
    )


def get_agent() -> CompiledStateGraph:
    """Return a configured agent or raise a clear credential error."""
    global _AGENT
    if not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("Set GROQ_API_KEY in .env before running the chat agent.")
    if _AGENT is None:
        _AGENT = build_agent()
    return _AGENT


def response_content(response: dict) -> str:
    """Extract the last assistant message from a LangGraph response."""
    messages = response.get("messages", [])
    if not messages:
        return "No response returned."
    return getattr(messages[-1], "content", str(messages[-1]))


def invoke_agent_messages(
    messages: Sequence[Any],
    thread_id: str = "default",
    attempts: int = 3,
) -> dict:
    """Invoke the agent with short retries for transient provider throttles."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return get_agent().invoke(
                {"messages": list(messages)},
                config={"configurable": {"thread_id": thread_id}},
            )
        except Exception as exc:
            last_error = exc
            if not _is_retryable_rate_limit(exc) or attempt == attempts - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Agent query failed after retries: {last_error}")


def run_agent(user_message: str, thread_id: str = "default") -> str:
    """Invoke the agent with conversation memory and return the final text."""
    response = invoke_agent_messages(
        [("user", user_message)],
        thread_id=thread_id,
    )
    return response_content(response)


def _is_retryable_rate_limit(exc: Exception) -> bool:
    """Retry only short provider throttles, not exhausted daily quota."""
    text = str(exc).lower()
    if "rate limit" not in text:
        return False
    if "tokens per day" in text or "tpd" in text:
        return False
    return True


agent = get_agent() if os.getenv("GROQ_API_KEY") else None
