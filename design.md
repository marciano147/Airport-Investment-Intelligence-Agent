# Design

## Goal

Build a one-day AI agent that helps airport modernization investors identify US airports with strong terminal or capacity expansion potential.

The agent must answer ranking, comparison, congestion, growth, long-haul, and unmet-demand questions. The original sample questions are examples only, not fixed scope.

## Architecture

```text
User question
  -> Streamlit chat UI
  -> LangGraph ReAct agent
  -> Tool calls for data and scoring
  -> Deterministic Python result
  -> LLM explanation with assumptions
```

Main files:

- `app.py`: Streamlit chat UI, example prompts, new-conversation control, and debug panel.
- `agent.py`: LangGraph ReAct agent, Groq model setup, tool registry, and `MemorySaver` checkpointing.
- `chat_store.py`: SQLite conversation list, message persistence, and JSON export.
- `tools.py`: LangChain tools for airport facts, congestion, passenger metrics, rankings, comparisons, and long-haul estimates.
- `data_loader.py`: public data caches, region/state handling, runway counts, and expansion candidate assembly.
- `scoring.py`: deterministic score calculation and ranking.
- `long_haul.py`: static long-haul and international share proxy table.
- `voice_utils.py`: Groq Whisper transcription helper for recorded questions.
- `context/*.md`: Hermes-style prompt context for role, tools, scoring, assumptions, and answer style.

The architecture has two explicit layers:

- LLM layer: `agent.py` interprets the analyst request, selects tools, keeps conversation context, and explains results.
- Compute layer: `tools.py`, `data_loader.py`, and `scoring.py` fetch/cache data, apply deterministic formulas, and return numeric outputs.

The LLM does not calculate rankings. It chooses tools and explains their outputs.

## Scoring Methodology

The composite score is fixed:

```text
Composite =
  (Congestion Score * 0.35) +
  (Passenger Growth Score * 0.30) +
  (Utilization Score * 0.25) +
  (Secondary Score * 0.10)
```

All component scores are normalized to 0-100 before weighting.

- Congestion Score: live FAA NAS Status traffic-management programs first, deterministic baseline tiers second. Ground delay programs use reported average delay minutes, arrival/departure delays use the midpoint of the reported range, and ground stops or closures use a high-pressure proxy. This prevents the highest-weight signal from collapsing to zero when the current FAA feed has no active program.
- Passenger Growth Score: year-over-year enplanement growth normalized from -5% to +12%.
- Utilization Score: passengers per runway, scaled relative to the selected candidate set and capped below full saturation before final normalization.
- Secondary Score: strategic proxy based on airport scale, long-haul route-mix estimate, and runway pressure. Defaults are explicit when richer data is unavailable.

The formula lives in `scoring.py`. Ranking order comes from pure Python, not from model preference.

## Recent Scoring Improvements

Utilization was upgraded from a static placeholder to a runway-based metric using OurAirports runway counts and FAA enplanements. This better reflects capacity pressure as passengers per runway.

Congestion now parses live FAA NAS Status programs for real delay minutes where available. If no program is active for an airport, deterministic hub baselines keep chronic congestion pressure from being treated as zero.

Secondary incorporates a long-haul and international share proxy, airport scale, and runway pressure to capture strategic terminal value for international and long-distance traffic.

## Data Sources

| Source | Used For | Current Handling |
| --- | --- | --- |
| OurAirports | Airport metadata, IATA coverage, runway data | Cached CSVs in `data/` |
| FAA passenger boarding data | Enplanements and YoY growth | Cached 2024 commercial-service CSV |
| FAA NAS airport status | Current ground delays, ground stops, closures, and arrival/departure delays | Live XML parse plus deterministic hub baseline |
| Static proxy tables | Long-haul, international share, and baseline congestion | Approximate, labeled in tool output and design notes |
| Groq Whisper | Voice question transcription | Optional Streamlit microphone flow |

## Where AI Is Used

The LLM is used for:

- Interpreting analyst questions.
- Choosing which tools to call.
- Combining tool results into a clear answer.
- Handling follow-up questions with conversation history.
- Stating assumptions and uncertainty.
- Transcribing recorded voice questions before normal agent handling.

Deterministic code is used for:

- Numerical scoring.
- Airport ranking order.
- Side-by-side comparison tables.
- Data loading and cache assembly.

## Monitoring and Debugging

- Tool failures are logged with Python logging.
- Tool calls log status and duration so slow data sources are visible during review.
- Cached airport, enplanement, region, candidate, and FAA status lookups reduce repeated compute-layer work.
- Tools return structured error payloads or fallback notes instead of failing silently.
- Streamlit can show raw agent responses in the debug panel.
- LangGraph memory uses a thread ID per Streamlit conversation.
- SQLite chat history stores prior conversations so the sidebar can restore them after refresh or restart. Restored conversations replay saved messages once on the next user turn so follow-up questions keep context even after process memory is gone.
- LangSmith tracing can be enabled through `.env` to inspect LLM steps and tool calls.
- Voice transcription returns visible errors instead of sending failed transcripts into the agent.

## Trade-Offs

- Cached FAA enplanement data keeps the demo stable, but it needs refresh work for future years.
- FAA NAS Status is a current traffic-management-program signal, not a full historical congestion model. It often returns no active program even for busy airports. Baseline congestion tiers are a deterministic fallback for one-day scope, not a substitute for historical OPSNET, ASPM, or BTS ASQP delay data.
- Long-haul share uses a transparent proxy because free route-level schedule data is limited.
- Utilization is based on passengers per runway. A production model should include BTS T-100 seats/departures, declared airport capacity, peak-hour operations, gates, terminal square footage, and airline constraints.
- Voice input is submit-after-recording, not a streaming voice assistant. That keeps the bonus feature simple and reviewable.
- The score is simple by design so reviewers can reproduce and challenge it.

## Assumptions and Limitations

- Passenger data has reporting lag.
- "Unmet demand" means a proxy based on congestion, growth, and utilization, not true origin-destination booking demand.
- Scope is limited to US airports with IATA codes and public data coverage.
- This is analyst decision support, not a construction-cost model, traffic forecast, or investment committee memo.

## Future Improvements

- Replace long-haul proxy values with BTS T-100 route-level data or a schedule feed.
- Replace baseline congestion tiers with FAA OPSNET, ASPM, or BTS delay history.
- Add OpenSky ADS-B density as an optional live operational-pressure signal.
- Add state and metro-area airport discovery beyond the current curated region map.
- Add a repeatable data refresh script for FAA enplanements.
- Add an evaluation set for example questions and expected tool calls.
- Persist conversation state outside process memory for deployed use.
