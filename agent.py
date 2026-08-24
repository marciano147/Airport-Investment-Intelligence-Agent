"""LangGraph agent wiring."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from prompts import load_context
from tools import (
    get_airport_info,
    get_congestion,
    get_passenger_metrics,
    rank_airports_for_expansion,
)


load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def build_agent():
    """Create the LangGraph agent after credentials are available."""
    llm = ChatOpenAI(model=MODEL, temperature=0)
    system_prompt = load_context()
    return create_react_agent(
        llm,
        tools=[
            get_airport_info,
            get_congestion,
            get_passenger_metrics,
            rank_airports_for_expansion,
        ],
        prompt=system_prompt,
    )


def get_agent():
    """Return a configured agent or raise a clear credential error."""
    if not os.getenv("OPENAI_API_KEY") and not os.getenv("OPENAI_ADMIN_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in .env before running the chat agent.")
    return build_agent()


agent = (
    build_agent()
    if os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_ADMIN_KEY")
    else None
)
