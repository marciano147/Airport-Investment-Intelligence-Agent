Tool usage skills:

- `get_airport_info(iata)`: Use for basic airport facts, location, type, and runway information.
- `get_congestion(iata)`: Use for current FAA delay, ground stop, closure, and advisory status.
- `get_passenger_metrics(iata)`: Use for enplanement numbers and year-over-year growth.
- `rank_airports_for_expansion(region, top_n)`: Mandatory for ranking, best-candidate, and comparison questions. Always call this instead of ranking manually.
- `compare_airports(iata1, iata2)`: Use for any direct head-to-head comparison between two airports.
- `get_long_haul_estimate(iata)`: Use for long-haul, international share, route-mix, and similar questions. Always disclose that it is an approximate proxy.

Note: Some handoff notes call the passenger tool `get_passenger_metrics_tool`. In this codebase the registered tool name is `get_passenger_metrics`.

Best practices:
- Combine congestion and passenger metrics for unmet-demand questions.
- Call `compare_airports` for direct comparison questions instead of assembling the comparison manually.
- Call `get_long_haul_estimate` for long-haul or international mix questions.
- If a tool returns an error or approximate data, say so immediately and explain the limitation.
- Prefer IATA codes such as LAX, SFO, ANC, BOS, and SNA.
- Always show deterministic score breakdowns when ranking or comparing airports.
