import agent
from langchain_core.messages import AIMessage


def test_agent_tools_include_comparison_and_long_haul():
    tool_names = {tool.name for tool in agent.AGENT_TOOLS}

    assert "compare_airports" in tool_names
    assert "get_long_haul_estimate" in tool_names
    assert "rank_airports_for_expansion" in tool_names


def test_agent_uses_memory_checkpointer():
    assert agent.CHECKPOINTER is not None


def test_response_content_extracts_last_message():
    response = {"messages": [AIMessage(content="first"), AIMessage(content="final")]}

    assert agent.response_content(response) == "final"
