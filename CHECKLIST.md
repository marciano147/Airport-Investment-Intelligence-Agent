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
- [x] Add Streamlit chat UI with debug sidebar.
- [x] Add README and design document.
- [x] Add tests for scoring and data assembly.

## Verification

- [x] Unit tests pass locally.
- [x] Streamlit boots locally with a dummy API key.
- [x] GitHub `main` has the initial implementation pushed.

## Follow-Up Improvements

- [ ] Automate FAA enplanement workbook refresh and schema validation.
- [ ] Add BTS T-100 route or operations data for a stronger utilization signal.
- [ ] Replace static long-haul proxy with BTS T-100 or schedule data.
- [ ] Add end-to-end mocked agent tests that do not call OpenAI.
- [ ] Add CI for pytest and import checks.
- [ ] Add screenshots or a short demo script for the take-home review.
