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
