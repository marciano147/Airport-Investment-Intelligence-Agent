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
    assert agent.MODEL == "llama-3.3-70b-versatile"


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
