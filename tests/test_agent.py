import agent
from langchain_core.messages import AIMessage


def test_agent_tools_include_comparison_and_long_haul():
    tool_names = {tool.name for tool in agent.AGENT_TOOLS}

    assert "compare_airports" in tool_names
    assert "get_long_haul_estimate" in tool_names
    assert "rank_airports_for_expansion" in tool_names


def test_agent_uses_memory_checkpointer():
    assert agent.CHECKPOINTER is not None


def test_agent_defaults_to_groq_model():
    assert agent.MODEL == "openai/gpt-oss-20b"
    assert agent.PROVIDER == "groq"
    assert agent.REASONING_FORMAT == "hidden"
    assert agent.REASONING_EFFORT == "low"
    assert agent.MAX_TOKENS == 1200
    assert agent.OPENROUTER_MODEL == "liquid/lfm-2.5-2.6b:free"


def test_get_agent_requires_groq_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    agent._AGENT = None

    try:
        agent.get_agent()
    except RuntimeError as exc:
        assert "GROQ_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected missing GROQ_API_KEY error")


def test_response_content_extracts_last_message():
    response = {"messages": [AIMessage(content="first"), AIMessage(content="final")]}

    assert agent.response_content(response) == "final"


def test_response_content_handles_empty_messages():
    assert agent.response_content({"messages": []}) == "No response returned."


def test_provider_diagnostics_are_safe_metadata():
    diagnostics = agent.provider_diagnostics(
        message_count=3,
        replay_mode="full_saved_history",
    )

    assert diagnostics["provider"] == "groq"
    assert diagnostics["model"] == "openai/gpt-oss-20b"
    assert diagnostics["message_count_sent"] == 3
    assert diagnostics["replay_mode"] == "full_saved_history"
    assert "api" not in diagnostics


def test_run_agent_invokes_configured_thread(monkeypatch):
    calls = {}

    class FakeAgent:
        def invoke(self, payload, config):
            calls["payload"] = payload
            calls["config"] = config
            return {"messages": [AIMessage(content="ranked")]}

    monkeypatch.setattr(agent, "get_agent", lambda: FakeAgent())

    result = agent.run_agent("Rank airports", thread_id="thread-123")

    assert result == "ranked"
    assert calls["payload"] == {"messages": [("user", "Rank airports")]}
    assert calls["config"] == {"configurable": {"thread_id": "thread-123"}}


def test_invoke_agent_messages_retries_rate_limits(monkeypatch):
    calls = {"count": 0, "sleeps": []}

    class FakeAgent:
        def invoke(self, payload, config):
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError("rate limit reached")
            calls["payload"] = payload
            calls["config"] = config
            return {"messages": [AIMessage(content="recovered")]}

    monkeypatch.setattr(agent, "get_agent", lambda: FakeAgent())
    monkeypatch.setattr(agent.time, "sleep", lambda seconds: calls["sleeps"].append(seconds))

    response = agent.invoke_agent_messages([("user", "Compare LAX and SNA")], "thread-456")

    assert agent.response_content(response) == "recovered"
    assert calls["count"] == 2
    assert calls["sleeps"] == [2]
    assert calls["payload"] == {"messages": [("user", "Compare LAX and SNA")]}
    assert calls["config"] == {"configurable": {"thread_id": "thread-456"}}


def test_invoke_agent_messages_does_not_retry_daily_quota(monkeypatch):
    calls = {"count": 0}

    class FakeAgent:
        def invoke(self, payload, config):
            calls["count"] += 1
            raise RuntimeError("rate limit reached on tokens per day")

    monkeypatch.setattr(agent, "get_agent", lambda: FakeAgent())

    try:
        agent.invoke_agent_messages([("user", "Rank airports")], "thread-789")
    except RuntimeError as exc:
        assert "tokens per day" in str(exc)
    else:
        raise AssertionError("Expected daily quota error")

    assert calls["count"] == 1


def test_format_agent_error_for_daily_quota():
    error = RuntimeError(
        "Rate limit reached on tokens per day. Please try again in 11m13.92s."
    )

    message = agent.format_agent_error(error)

    assert "daily quota is exhausted" in message
    assert "Retry in 11m13.92s" in message
    assert "rate_limit_exceeded" not in message


def test_format_agent_error_for_request_too_large():
    error = RuntimeError(
        "Request too large for model qwen/qwen3.6-27b on tokens per minute "
        "(TPM): Limit 8000, Requested 8459, please reduce your message size."
    )

    message = agent.format_agent_error(error)

    assert "request is too large" in message
    assert "full-history replay" in message
    assert "8459" not in message
