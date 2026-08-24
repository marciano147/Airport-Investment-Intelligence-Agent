Deterministic scoring methodology:

Composite Score =
  (Congestion Score * 0.35) +
  (Passenger Growth Score * 0.30) +
  (Utilization Score * 0.25) +
  (Secondary Score * 0.10)

All component scores must be normalized to 0-100 before weighting.

Definitions:
- Congestion: Combines live FAA delay/advisory minutes with deterministic baseline tiers for major hubs when the live feed has no active delay.
- Passenger Growth: Year-over-year enplanement percentage change, normalized against a -5% to +12% range.
- Utilization: Passenger volume per runway relative to selected peer airports, capped below full saturation.
- Secondary: Strategic context from airport scale, long-haul proxy, and runway pressure. Defaults are explicit when richer data is unavailable.

Always show the full breakdown in answers, not just the final composite score.

Higher composite means a stronger candidate for capacity-related investment.
