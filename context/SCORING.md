Deterministic scoring methodology:

Composite Score =
  (Congestion Score * 0.35) +
  (Passenger Growth Score * 0.30) +
  (Utilization Score * 0.25) +
  (Secondary Score * 0.10)

Unmet Demand Pressure =
  (Congestion Score * 0.40) +
  (Utilization Score * 0.35) +
  (Passenger Growth Score * 0.25)

All component scores must be normalized to 0-100 before weighting.

Definitions:
- Congestion: Live FAA NAS Status delay minutes when an active traffic-management program exists, blended with a labeled structural baseline from `data/congestion_baselines.csv`. If no live program exists, the baseline is used as-is. Always report current FAA delay, structural baseline, and final congestion score separately.
- Passenger Growth: Year-over-year enplanement percentage change, normalized against a -5% to +12% range.
- Utilization: Passengers per runway on a fixed 1,000,000 to 8,000,000 scale. The same airport keeps the same utilization score in national rankings, regional rankings, and pairwise comparisons.
- Secondary: Strategic context from long-haul share proxy, airport scale, and runway pressure. The long-haul component starts at 40, adds 0.95 points per long-haul percentage point, and caps at 88 before blending with scale and runway pressure.
- Unmet Demand Pressure: A proxy index from congestion, utilization, and growth. Classification is High (>=70), Moderate (>=50), or Limited. It is not unserved flights or origin-destination booking demand.

Congestion is weighted most in the composite score because operating pressure is the clearest available constraint signal. Growth is a forward-looking modifier, utilization measures runway pressure, and secondary factors are down-weighted because they rely more on proxies. Unmet-demand pressure emphasizes congestion and utilization for the same reason. The 1M–8M passengers-per-runway range is a prototype bound so peer selection cannot change an airport's utilization score; it is not an FAA threshold.

Always show the full breakdown in answers, not just the final composite score.

Higher composite means a stronger candidate for capacity-related investment.
