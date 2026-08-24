"""LLM layer: question routing, tool selection, and response synthesis."""

from __future__ import annotations

import os
import re
import time
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv
from langchain_groq import ChatGroq
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

# LLM configuration lives here. The compute layer stays in `tools.py`,
# `data_loader.py`, and `scoring.py`, so the model routes questions but does not
# invent rankings or calculate scores itself.
PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "liquid/lfm-2.5-2.6b:free")
MODEL = OPENROUTER_MODEL if PROVIDER == "openrouter" else GROQ_MODEL
FALLBACK_ENABLED = os.getenv("LLM_FALLBACK_ENABLED", "true").strip().lower() == "true"
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", os.getenv("GROQ_MAX_TOKENS", "1200")))
TIMEOUT_SECONDS = float(
    os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("GROQ_TIMEOUT_SECONDS", "45"))
)
REASONING_FORMAT = os.getenv("GROQ_REASONING_FORMAT", "hidden")
REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT") or (
    "none" if MODEL.startswith("qwen/") else "low"
)
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_APP_URL = os.getenv(
    "OPENROUTER_APP_URL",
    "https://github.com/marciano147/Airport-Investment-Intelligence-Agent",
)
OPENROUTER_APP_NAME = os.getenv(
    "OPENROUTER_APP_NAME",
    "Airport Investment Intelligence Agent",
)
CHECKPOINTER = MemorySaver()
_ACTIVE_PROVIDER = PROVIDER
_ACTIVE_MODEL = MODEL

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
_OPENROUTER_AGENT: CompiledStateGraph | None = None


def build_agent(provider: str | None = None) -> CompiledStateGraph:
    """Create a LangGraph agent for the requested provider."""
    selected_provider = (provider or PROVIDER).strip().lower()
    if selected_provider == "openrouter":
        llm = ChatOpenAI(
            model=OPENROUTER_MODEL,
            temperature=0,
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url=OPENROUTER_BASE_URL,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT_SECONDS,
            max_retries=1,
            default_headers={
                "HTTP-Referer": OPENROUTER_APP_URL,
                "X-Title": OPENROUTER_APP_NAME,
            },
        )
    else:
        llm = ChatGroq(
            model=GROQ_MODEL,
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY"),
            reasoning_format=REASONING_FORMAT,
            reasoning_effort=REASONING_EFFORT,
            max_tokens=MAX_TOKENS,
            timeout=TIMEOUT_SECONDS,
            max_retries=1,
        )
    system_prompt = load_context()
    return create_react_agent(
        llm,
        tools=AGENT_TOOLS,
        prompt=system_prompt,
        checkpointer=CHECKPOINTER,
    )


def get_agent() -> CompiledStateGraph:
    """Return a configured agent or raise a clear credential error."""
    global _AGENT, _OPENROUTER_AGENT, _ACTIVE_PROVIDER, _ACTIVE_MODEL
    if PROVIDER == "openrouter" and not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("Set OPENROUTER_API_KEY in .env before using OpenRouter.")
    if PROVIDER != "openrouter" and not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("Set GROQ_API_KEY in .env before running the chat agent.")
    if PROVIDER == "openrouter":
        if _OPENROUTER_AGENT is None:
            _OPENROUTER_AGENT = build_agent("openrouter")
        _ACTIVE_PROVIDER = "openrouter"
        _ACTIVE_MODEL = OPENROUTER_MODEL
        return _OPENROUTER_AGENT
    if _AGENT is None:
        _AGENT = build_agent("groq")
    _ACTIVE_PROVIDER = "groq"
    _ACTIVE_MODEL = GROQ_MODEL
    return _AGENT


def get_openrouter_agent() -> CompiledStateGraph:
    """Return the OpenRouter fallback agent when its key is configured."""
    global _OPENROUTER_AGENT, _ACTIVE_PROVIDER, _ACTIVE_MODEL
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("Set OPENROUTER_API_KEY in .env before using OpenRouter.")
    if _OPENROUTER_AGENT is None:
        _OPENROUTER_AGENT = build_agent("openrouter")
    _ACTIVE_PROVIDER = "openrouter"
    _ACTIVE_MODEL = OPENROUTER_MODEL
    return _OPENROUTER_AGENT


def has_provider_key() -> bool:
    """Return whether the selected LLM provider has credentials configured."""
    if PROVIDER == "openrouter":
        return bool(os.getenv("OPENROUTER_API_KEY"))
    return bool(os.getenv("GROQ_API_KEY"))


def has_fallback_key() -> bool:
    """Return whether OpenRouter can be used as automatic fallback."""
    return bool(os.getenv("OPENROUTER_API_KEY"))


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
    """Invoke the agent, falling back from Groq to OpenRouter when configured."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return get_agent().invoke(
                {"messages": list(messages)},
                config={"configurable": {"thread_id": thread_id}},
            )
        except Exception as exc:
            last_error = exc
            if _should_fallback_to_openrouter(exc):
                return get_openrouter_agent().invoke(
                    {"messages": list(messages)},
                    config={"configurable": {"thread_id": f"{thread_id}-openrouter"}},
                )
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
    if "tokens per day" in text or "tpd" in text or "request too large" in text:
        return False
    return True


def _should_fallback_to_openrouter(exc: Exception) -> bool:
    """Use OpenRouter when Groq fails with a quota or size limit."""
    if PROVIDER == "openrouter" or not FALLBACK_ENABLED or not has_fallback_key():
        return False
    text = str(exc).lower()
    fallback_markers = [
        "tokens per day",
        "tpd",
        "request too large",
        "tokens per minute",
        "tpm",
        "rate limit",
        "timeout",
        "timed out",
    ]
    return any(marker in text for marker in fallback_markers)


def provider_diagnostics(message_count: int, replay_mode: str) -> dict[str, Any]:
    """Return safe debug metadata for the last agent request."""
    return {
        "configured_provider": PROVIDER,
        "active_provider": _ACTIVE_PROVIDER,
        "model": _ACTIVE_MODEL,
        "fallback_enabled": FALLBACK_ENABLED,
        "fallback_configured": has_fallback_key(),
        "message_count_sent": message_count,
        "replay_mode": replay_mode,
        "max_tokens": MAX_TOKENS,
        "timeout_seconds": TIMEOUT_SECONDS,
    }


def format_agent_error(exc: Exception) -> str:
    """Convert provider errors into concise user-facing recovery guidance."""
    text = str(exc)
    lower = text.lower()
    retry = _extract_retry_after(text)

    if "tokens per day" in lower or "tpd" in lower:
        wait = f" Retry in {retry}." if retry else ""
        return (
            f"LLM daily quota is exhausted for `{_ACTIVE_MODEL}`.{wait} "
            "If OpenRouter is configured, the app will try that fallback automatically."
        )

    if "request too large" in lower or "tokens per minute" in lower or "tpm" in lower:
        wait = f" Retry in {retry}." if retry else ""
        return (
            f"The request is too large for `{_ACTIVE_MODEL}` under the current token limit.{wait} "
            "Turn off full-history replay for restored chats, start a new conversation, "
            "or use a model with a larger token budget."
        )

    if "rate limit" in lower:
        wait = f" Retry in {retry}." if retry else ""
        return f"LLM rate limit reached for `{_ACTIVE_MODEL}`.{wait}"

    return f"Agent error: {exc}"


def _extract_retry_after(text: str) -> str | None:
    """Extract provider retry guidance from common quota error strings."""
    match = re.search(
        r"try again in ([0-9.]+[a-z](?:[0-9.]+[a-z])*)",
        text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    match = re.search(r"retry-after['\"]?: ['\"]?([^,'\"}]+)", text, re.IGNORECASE)
    return match.group(1).strip() if match else None


agent = get_agent() if has_provider_key() else None
