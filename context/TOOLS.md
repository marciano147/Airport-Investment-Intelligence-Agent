Tool usage skills:

- `get_airport_info(iata)`: Use for basic airport facts, location, type, and runway information.
- `get_congestion(iata)`: Use for current FAA NAS Status programs: ground delay programs, ground stops, closures, and arrival/departure delays. Always report live delay separately from the structural congestion baseline.
- `get_passenger_metrics(iata)`: Use for enplanement numbers and year-over-year growth.
- `rank_airports_for_expansion(region, top_n)`: Mandatory for ranking, best-candidate, and comparison questions. Always call this instead of ranking manually.
- `compare_airports(iata1, iata2)`: Use for any direct head-to-head comparison between two airports. Copy unmet-demand pressure from the tool row. Do not guess High/Moderate/Limited.
- `get_long_haul_estimate(iata)`: Use for long-haul, international share, route-mix, and similar questions. Always label the result as an estimated long-haul share proxy, not current schedule data.
- `get_unmet_demand(iata)`: Mandatory for unmet-demand, unserved-demand, and capacity-pressure questions. Always call this instead of combining congestion and passenger metrics by hand. Call it a pressure index/proxy, never "X unserved flights." Never invent a pressure score or classification.

Note: Some handoff notes call the passenger tool `get_passenger_metrics_tool`. In this codebase the registered tool name is `get_passenger_metrics`.

Best practices:
- Call `get_unmet_demand` for unmet-demand questions. State that it is a proxy index, not booking or unserved-flight data.
- If NAS Status reports an active program, explain that the delay minutes come from the live FAA feed and are blended with the structural baseline.
- If NAS Status has no active program, explain that the congestion score uses the labeled prototype structural baseline instead of treating congestion as zero. Do not call those baselines "FAA scores"; they live in `data/congestion_baselines.csv`.
- Call `compare_airports` for direct comparison questions instead of assembling the comparison manually.
- Never invent unmet-demand pressure scores or High/Moderate/Limited labels. Use `get_unmet_demand` or the comparison tool's unmet-demand pressure row.
- Call `get_long_haul_estimate` for long-haul or international mix questions.
- If a tool returns an error or approximate data, say so immediately and explain the limitation.
- Prefer IATA codes such as LAX, SFO, ANC, BOS, and SNA.
- Always show deterministic score breakdowns when ranking or comparing airports.
