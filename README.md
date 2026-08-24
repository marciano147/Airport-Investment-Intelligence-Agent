# Airport Investment Intelligence Agent

AI decision-support agent for identifying US airports with promising terminal or capacity expansion potential.

The app uses deterministic scoring for ranking and an LLM only for conversation, explanation, and follow-up handling.

## Features

- LangGraph + LangChain agent
- Streamlit chat UI
- Hermes-style markdown context files
- Deterministic scoring breakdown
- Cached public airport data
- Runway-aware utilization proxy
- Direct airport comparison tool
- Approximate long-haul / international share proxy
- Live FAA NAS delay status where available
- LangSmith tracing hooks
- In-memory LangGraph checkpointer for follow-up questions
- New-conversation control and debug panel in Streamlit
- Unit tests for scoring and data assembly

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set `OPENAI_API_KEY` in `.env`, then run:

```bash
streamlit run app.py
```

Run tests:

```bash
pytest tests/ -v
```

## Optional LangSmith Tracing

```bash
export LANGSMITH_TRACING=true
export LANGSMITH_API_KEY=
export LANGSMITH_PROJECT=airport-agent
```

Every tool call and LLM step will appear in the LangSmith project.

## Data Sources

- Airport metadata and runway counts: OurAirports CSV cache.
- Passenger metrics: cached FAA 2024 commercial-service passenger boarding/enplanement workbook.
- Congestion: live FAA NAS airport status feed where available.

The checked-in CSVs make the one-day demo reliable. Refresh logic is included for airport and runway metadata; enplanement refresh should be reviewed when FAA workbook formats change.

## Example Questions

- Rank the top 5 US airports for terminal expansion.
- Rank California airports for capacity investment potential.
- Which airports in New England are strong candidates?
- Compare LAX and SNA congestion levels.
- Estimate long-haul share at ANC.
- Why did the top airport score higher than the others?
- What assumptions should I know before using this ranking?
