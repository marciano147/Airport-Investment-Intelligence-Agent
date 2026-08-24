import agent


def test_agent_tools_include_comparison_and_long_haul():
    tool_names = {tool.name for tool in agent.AGENT_TOOLS}

    assert "compare_airports" in tool_names
    assert "get_long_haul_estimate" in tool_names
    assert "rank_airports_for_expansion" in tool_names


def test_agent_uses_memory_checkpointer():
    assert agent.CHECKPOINTER is not None
