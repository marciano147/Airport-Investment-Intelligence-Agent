"""LLM layer: question routing, tool selection, and response synthesis."""

from __future__ import annotations

import os

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
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
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


def run_agent(user_message: str, thread_id: str = "default") -> str:
    """Invoke the agent with conversation memory and return the final text."""
    response = get_agent().invoke(
        {"messages": [("user", user_message)]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return response_content(response)


agent = get_agent() if os.getenv("GROQ_API_KEY") else None
