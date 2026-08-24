# Design

## Goal

Build a one-day AI agent that helps an airport modernization investor identify promising US airports for terminal or capacity expansion.

The agent must rank airports with deterministic logic, explain the reasoning, show assumptions, and support conversational follow-ups.

## Architecture

- `app.py`: Streamlit chat UI and debug sidebar.
- `agent.py`: LangGraph ReAct agent using OpenAI chat models.
- `tools.py`: LangChain tools for airport info, congestion, passenger metrics, and ranking.
- `long_haul.py`: static, documented proxy for long-haul and international share questions.
- `scoring.py`: deterministic scoring formula.
- `data_loader.py`: cached public data loading, region mapping, and ranking candidate assembly.
- `context/*.md`: Hermes-style behavioral context.

The LLM does not decide rankings. It calls tools, then explains deterministic outputs.

The example questions are illustrations, not fixed scope. The same tools support region rankings, direct airport comparisons, single-airport checks, long-haul proxy questions, and follow-ups.

## Scoring Methodology

Required formula:

```text
Composite = (Congestion * 0.35) + (Growth * 0.30) + (Utilization * 0.25) + (Secondary * 0.10)
```

Each component is normalized to 0-100.

- Congestion: live FAA delay/advisory proxy where available, normalized from 0 to 60 minutes.
- Growth: year-over-year passenger growth, normalized from -5% to +20%.
- Utilization: 2024 enplanements per runway relative to the selected region.
- Secondary: inverse size proxy for non-dominant market opportunity.

## Data Sources & Limitations

- OurAirports provides airport metadata and IATA/state coverage.
- FAA passenger boarding data is the target source for passenger metrics, but it has reporting lag.
- FAA NAS status is live, but active advisories are sparse and not a complete congestion model.
- The included enplanement CSV is a cache from the FAA 2024 commercial-service workbook and should be refreshed before production use.
- Region support covers major US airports by default, named prototype regions, and state-code filters.
- Long-haul share is a static proxy table in v1. Replace it with route-level BTS T-100 or commercial schedule data for production.

## Hermes-Style Context System

`prompts.py` loads:

- `SOUL.md`
- `TOOLS.md`
- `SCORING.md`
- `ASSUMPTIONS.md`
- `WRITING.md`

This keeps agent behavior editable without changing code.

## Monitoring & Debugging

- Python logging wraps tool failures.
- Tools return structured errors with suggestions.
- Streamlit exposes a raw-response debug panel.
- LangGraph uses an in-memory checkpointer keyed by the Streamlit session thread for follow-up questions.
- LangSmith tracing can be enabled with environment variables.

## Trade-Offs

- The one-day build favors reliable cached data over fragile live workbook parsing.
- The score is intentionally transparent and deterministic.
- The model is useful for conversation and explanation, not numeric authority.

## Assumptions & Uncertainty

- Long-haul share is not modeled in v1.
- Unmet demand is a proxy.
- This is not a full financial model.
