# Build Checklist

## Completed

- [x] Scaffold Streamlit, LangGraph, LangChain, and LangSmith-ready project.
- [x] Add Hermes-style context files.
- [x] Implement deterministic scoring with full component breakdown.
- [x] Cache public OurAirports airport metadata.
- [x] Cache OurAirports runway counts for utilization proxy.
- [x] Cache FAA 2024 commercial-service enplanements for broad US coverage.
- [x] Add dynamic region support for US, all, state codes, and named prototype regions.
- [x] Default ranking scope to major US airports instead of New England.
- [x] Add FAA NAS live delay/advisory lookup with XML parsing.
- [x] Add direct airport comparison tool.
- [x] Add approximate long-haul share proxy tool.
- [x] Wire LangGraph in-memory checkpointer for follow-up questions.
- [x] Add reusable `run_agent` helper for memory-backed invocation.
- [x] Add Streamlit chat UI with debug sidebar.
- [x] Add Streamlit new-conversation control and broader example questions.
- [x] Switch chat LLM provider to Groq.
- [x] Add Streamlit voice input with Groq Whisper transcription.
- [x] Document LangSmith EU endpoint for tracing.
- [x] Add README and design document.
- [x] Document Windows venv activation, pip install, and common local-run errors.
- [x] Add tests for scoring and data assembly.
- [x] Add CI-safe tests for tools, prompts, voice, app render, and edge cases.
- [x] Add opt-in live smoke script for Groq, Whisper, LangSmith, and Streamlit.
- [x] Add compute-layer caches and tool timing logs.
- [x] Add persistent SQLite chat history and move voice input near the chat box.

## Verification

- [x] Unit tests pass locally.
- [x] Streamlit boots locally with a dummy API key.
- [x] GitHub `main` has the initial implementation pushed.

## Follow-Up Improvements

- [ ] Automate FAA enplanement workbook refresh and schema validation.
- [ ] Add BTS T-100 route or operations data for a stronger utilization signal.
- [ ] Replace static long-haul proxy with BTS T-100 or schedule data.
- [ ] Add CI for pytest and import checks.
- [ ] Add screenshots for the take-home review.
