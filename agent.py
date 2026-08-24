"""LangGraph agent wiring."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
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

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CHECKPOINTER = MemorySaver()
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
    llm = ChatOpenAI(model=MODEL, temperature=0)
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
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_ADMIN_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in .env before running the chat agent.")
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


agent = get_agent() if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_ADMIN_KEY") else None
