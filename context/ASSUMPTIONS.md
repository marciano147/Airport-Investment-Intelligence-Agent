Assumptions, uncertainty, and scoping:

- Data sources are public and free: FAA, OurAirports, and FAA/BTS passenger datasets.
- Passenger statistics usually lag by several months.
- "Unmet demand" is a pressure-index proxy from congestion, utilization, and growth. It is not true origin-destination booking data or a count of unserved flights.
- Congestion uses live FAA NAS Status traffic-management programs when present. If no active program exists, labeled prototype structural baselines from `data/congestion_baselines.csv` are applied so chronic pressure is not treated as zero.
- Estimated long-haul share is an approximate proxy, not live schedule data.
- Scope is limited to primary commercial US airports that have IATA codes.
- This is an analyst decision-support tool only. It does not include construction costs, airline agreements, political factors, or full financial modeling.
- When a user specifies a region such as New England, California, Texas, or Midwest, filter to relevant airports in that region. If no region is given, default to major US airports.
