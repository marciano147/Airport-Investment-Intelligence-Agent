# Airport Investment Intelligence Agent

AI decision-support agent for identifying US airports with promising terminal or capacity expansion potential.

The agent uses deterministic Python scoring for rankings and comparisons. The LLM handles question routing, tool selection, explanation, and conversational follow-ups.

## Features

- Rank US airports by expansion opportunity using a fixed scoring formula.
- Compare any two airports on congestion, passenger growth, utilization, and composite score.
- Use calibrated congestion baselines when the live FAA feed has no active delay advisories.
- Estimate long-haul or international share with a labeled proxy table.
- Answer follow-up questions through LangGraph conversation memory.
- Record a voice question in Streamlit and transcribe it with Groq Whisper.
- Reopen and export past conversations from local SQLite chat history.
- Show assumptions, data limits, and score breakdowns.
- Inspect raw agent responses in the Streamlit debug panel.
- Enable LangSmith tracing for tool and LLM review.

## Tech Stack

- LangGraph and LangChain
- Groq chat model through `langchain-groq`
- Groq Whisper speech-to-text through the `groq` SDK
- Streamlit chat UI
- Public aviation data from OurAirports, FAA passenger boarding data, and FAA NAS status
- Pytest for deterministic scoring and tool tests

## Setup

This is a Python project. Do not run `npm i`.

Prerequisites: Python 3.11+ (3.12 works). Create a virtual environment, install `requirements.txt`, then copy `.env.example` to `.env`.

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

**Windows (Git Bash):**

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The venv must stay activated for `streamlit`, `pytest`, and `pip`. If you open a new terminal, activate it again.

Edit `.env`:

```bash
GROQ_API_KEY=gsk-your-key-here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_TRANSCRIPTION_MODEL=whisper-large-v3-turbo
```

`GROQ_API_KEY` is required for both chat and voice transcription. `GROQ_MODEL` and `GROQ_TRANSCRIPTION_MODEL` are optional defaults.

Create a Groq key at `https://console.groq.com/keys`.

Optional LangSmith tracing:

```bash
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
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

With the venv activated:

```bash
streamlit run app.py
```

If `streamlit` is not on your PATH, call it from the venv:

```bash
# Windows
.venv\Scripts\streamlit.exe run app.py

# macOS / Linux
.venv/bin/streamlit run app.py
```

Voice input appears in the left sidebar under Controls. Record a question, then click `Send Voice`; the app transcribes the audio and submits the transcript as a normal chat message. Past conversations appear in the sidebar and are stored locally in `data/chat_history.db`; when you reopen one, the saved context is replayed on the next message so follow-ups still work.

## Troubleshooting

**`streamlit: command not found`**  
The venv is not activated, or Streamlit is not installed in it. Activate `.venv`, then run `pip install -r requirements.txt`. On Windows Git Bash the activate script is `source .venv/Scripts/activate`, not `source .venv/bin/activate`.

**`ModuleNotFoundError: No module named 'langchain_groq'`** (or another package from `requirements.txt`)  
Dependencies were not fully installed. With the venv activated, run `pip install -r requirements.txt`, then refresh the Streamlit page or restart the server.

**`npm i` / Node**  
There is no `package.json`. Install with `pip`, not npm.

## Test

Offline tests do not call Groq, LangSmith, FAA, or Streamlit over the network:

```bash
pytest tests/ -v
```

Opt-in live smoke checks use `.env` and real services:

```bash
python scripts/live_smoke.py
```

The live smoke script checks Groq model access, one agent query, LangSmith access, Groq Whisper transcription, and Streamlit health.

For a broader live e2e and edge-case audit:

```bash
python scripts/e2e_edge_cases.py
```

This checks tool rankings, comparisons, long-haul estimates, invalid inputs, empty regions, several live agent questions, same-thread follow-up memory, voice transcription, and Streamlit boot.

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
chat_store.py   SQLite conversation history store
tools.py        LangChain tools for rankings, comparisons, long-haul, and airport data
data_loader.py  Cached public data loading and candidate assembly
scoring.py      Deterministic scoring model
long_haul.py    Long-haul proxy estimates
voice_utils.py  Groq Whisper transcription helper
prompts.py      Hermes-style context loader
context/        SOUL, TOOLS, SCORING, ASSUMPTIONS, and WRITING prompts
tests/          Unit tests
scripts/        Opt-in live smoke checks
design.md       Architecture and scoring notes
```

## Notes

This is a one-day prototype. It uses public data and transparent proxies, so it should be treated as analyst decision support, not a financial model.
