Tool usage skills:

- `get_airport_info(iata)`: Use for basic airport facts, location, type, and runway information.
- `get_congestion(iata)`: Use for current FAA delay, ground stop, closure, and advisory status.
- `get_passenger_metrics(iata)`: Use for enplanement numbers and year-over-year growth.
- `rank_airports_for_expansion(region, top_n)`: Mandatory for ranking, best-candidate, and comparison questions. Always call this instead of ranking manually.

Best practices:
- Combine congestion and passenger metrics for unmet-demand questions.
- If a tool returns an error or approximate data, say so immediately and explain the limitation.
- Prefer IATA codes such as LAX, SFO, ANC, BOS, and SNA.
