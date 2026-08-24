Assumptions, uncertainty, and scoping:

- Data sources are public and free: FAA, OurAirports, and FAA/BTS passenger datasets.
- Passenger statistics usually lag by several months.
- "Unmet demand" is a proxy based on high congestion, strong growth, and high utilization. It is not true origin-destination booking data.
- Congestion uses live FAA delay advisories when available and deterministic hub baselines when the live feed has no active events.
- Long-haul percentage is an approximate proxy, not live schedule data.
- Scope is limited to primary commercial US airports that have IATA codes.
- This is an analyst decision-support tool only. It does not include construction costs, airline agreements, political factors, or full financial modeling.
- When a user specifies a region such as New England, California, Texas, or Midwest, filter to relevant airports in that region. If no region is given, default to major US airports.
