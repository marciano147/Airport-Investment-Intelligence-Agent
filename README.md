# Airport Investment Intelligence Agent

AI decision-support agent for identifying US airports with promising terminal or capacity expansion potential.

The agent uses deterministic Python scoring for rankings and comparisons. The LLM handles question routing, tool selection, explanation, and conversational follow-ups.

## Features

- Rank US airports by expansion opportunity using a fixed scoring formula.
- Compare any two airports on congestion, passenger growth, utilization, and composite score.
- Estimate long-haul or international share with a labeled proxy table.
- Answer follow-up questions through LangGraph conversation memory.
- Show assumptions, data limits, and score breakdowns.
- Inspect raw agent responses in the Streamlit debug panel.
- Enable LangSmith tracing for tool and LLM review.

## Tech Stack

- LangGraph and LangChain
- OpenAI chat model through `langchain-openai`
- Streamlit chat UI
- Public aviation data from OurAirports, FAA passenger boarding data, and FAA NAS status
- Pytest for deterministic scoring and tool tests

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_API_KEY` is required to run the chat agent. `OPENAI_MODEL` is optional and defaults to `gpt-4o-mini`.

Optional LangSmith tracing:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=airport-agent
```

## Data

The repo includes demo-ready CSV caches:

- `data/airports.csv`: US scheduled-service airport metadata from OurAirports.
- `data/runways.csv`: runway counts and longest-runway fields derived from OurAirports.
- `data/enplanements.csv`: FAA 2024 commercial-service passenger boarding cache.

Airport and runway caches can refresh automatically if missing. The enplanement cache is checked in for review stability and should be refreshed manually when FAA workbook formats or reporting years change.

## Run

```bash
streamlit run app.py
```

## Test

```bash
pytest tests/ -v
```

## Example Questions

- Rank the top 5 US airports for terminal expansion.
- Rank California airports for capacity investment potential.
- Which airports in New England are strong candidates?
- Compare LAX and SNA congestion levels.
- Estimate long-haul share at ANC.
- What is the unmet flight demand at SFO and why?
- Why did the top airport score higher than the others?

## Project Structure

```text
app.py          Streamlit chat UI and debug panel
agent.py        LangGraph agent, tool registry, and memory helper
tools.py        LangChain tools for rankings, comparisons, long-haul, and airport data
data_loader.py  Cached public data loading and candidate assembly
scoring.py      Deterministic scoring model
long_haul.py    Long-haul proxy estimates
prompts.py      Hermes-style context loader
context/        SOUL, TOOLS, SCORING, ASSUMPTIONS, and WRITING prompts
tests/          Unit tests
design.md       Architecture and scoring notes
```

## Notes

This is a one-day prototype. It uses public data and transparent proxies, so it should be treated as analyst decision support, not a financial model.
