"""Opt-in end-to-end and edge-case checks for the airport agent.

Run with:
    python scripts/e2e_edge_cases.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


Check = Callable[[], str]


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)
    os.chdir(ROOT)

    # These are intentionally public-seam checks: tool invocations, agent helper
    # calls, voice transcription, and Streamlit boot. They avoid internal mocks.
    checks: list[tuple[str, Check]] = [
        ("environment", check_environment),
        ("tool ranking", check_tool_ranking),
        ("tool comparison", check_tool_comparison),
        ("tool long haul", check_tool_long_haul),
        ("tool invalid airport", check_tool_invalid_airport),
        ("tool empty region", check_tool_empty_region),
        ("agent ranking", check_agent_ranking),
        ("agent comparison", check_agent_comparison),
        ("agent long haul", check_agent_long_haul),
        ("agent follow-up memory", check_agent_follow_up),
        ("voice transcription", check_voice_transcription),
        ("streamlit boot", check_streamlit_boot),
    ]

    failed = False
    for label, check in checks:
        try:
            detail = check()
            print(f"PASS {label}: {detail}")
        except SkipCheck as exc:
            print(f"SKIP {label}: {exc}")
        except Exception as exc:
            failed = True
            print(f"FAIL {label}: {type(exc).__name__}: {exc}")

    return 1 if failed else 0


def check_environment() -> str:
    required = ["GROQ_API_KEY", "GROQ_MODEL", "GROQ_TRANSCRIPTION_MODEL"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"missing required env vars: {', '.join(missing)}")
    return "required live env vars are set"


def check_tool_ranking() -> str:
    from tools import rank_airports_for_expansion

    result = rank_airports_for_expansion.invoke({"region": "US", "top_n": 5})
    _require_fragments(
        result,
        ["Ranking for region: US", "Composite", "Congestion", "Secondary", "Assumptions"],
    )
    return "US ranking includes score table and assumptions"


def check_tool_comparison() -> str:
    from tools import compare_airports

    result = compare_airports.invoke({"iata1": "LAX", "iata2": "SNA"})
    _require_fragments(
        result,
        ["Comparison: LAX vs SNA", "Composite score", "Estimated long-haul share proxy"],
    )
    return "LAX/SNA comparison includes KPIs and score breakdown"


def check_tool_long_haul() -> str:
    from tools import get_long_haul_estimate

    known = get_long_haul_estimate.invoke({"iata": "ANC"})
    unknown = get_long_haul_estimate.invoke({"iata": "ZZZ"})
    if known.get("long_haul_share_proxy_pct") != 35:
        raise RuntimeError(f"unexpected ANC long-haul estimate: {known}")
    if unknown.get("long_haul_share_proxy_pct") is not None:
        raise RuntimeError(f"unknown airport should not get estimate: {unknown}")
    return "known and unknown long-haul paths behave correctly"


def check_tool_invalid_airport() -> str:
    from tools import get_airport_info, get_passenger_metrics

    airport = get_airport_info.invoke({"iata": "ZZZ"})
    metrics = get_passenger_metrics.invoke({"iata": "ZZZ"})
    if "error" not in airport or "error" not in metrics:
        raise RuntimeError(f"invalid airport did not return errors: {airport}, {metrics}")
    return "invalid IATA returns structured errors"


def check_tool_empty_region() -> str:
    from tools import rank_airports_for_expansion

    result = rank_airports_for_expansion.invoke({"region": "ZZ", "top_n": 3})
    _require_fragments(result, ["No candidate airports found"])
    return "unknown state/empty region returns a clear message"


def check_agent_ranking() -> str:
    answer = _run_agent_with_retry(
        "Rank the top 3 California airports for capacity investment. Show score breakdown.",
        thread_id=_thread_id("agent-ranking"),
    )
    _require_fragments(answer, ["Composite", "Congestion", "Utilization"])
    return "agent answered ranking through tool-backed score table"


def check_agent_comparison() -> str:
    answer = _run_agent_with_retry(
        "Compare LAX and SNA on congestion, growth, utilization, and composite score.",
        thread_id=_thread_id("agent-comparison"),
    )
    _require_fragments(answer, ["LAX", "SNA", "Composite"])
    return "agent answered direct airport comparison"


def check_agent_long_haul() -> str:
    answer = _run_agent_with_retry(
        "What is the long-haul flight share estimate for ANC? Keep it short.",
        thread_id=_thread_id("agent-long-haul"),
    )
    _require_fragments(answer, ["ANC", "35"])
    return "agent used long-haul proxy for ANC"


def check_agent_follow_up() -> str:
    # Same thread ID verifies LangGraph's MemorySaver path, which is what the
    # Streamlit app depends on for natural follow-up questions.
    thread_id = _thread_id("agent-follow-up")
    first = _run_agent_with_retry(
        "Rank the top 3 US airports for terminal expansion. Keep the table.",
        thread_id=thread_id,
    )
    _require_fragments(first, ["Composite", "Congestion"])

    second = _run_agent_with_retry(
        "Now explain why #1 ranked above #2 in one short paragraph.",
        thread_id=thread_id,
    )
    _require_fragments(second, ["ATL", "CLT", "composite"])
    return "same-thread follow-up returned contextual explanation"


def check_voice_transcription() -> str:
    from scripts.live_smoke import check_whisper

    return check_whisper()


def check_streamlit_boot() -> str:
    from scripts.live_smoke import check_streamlit_boot as live_check

    return live_check()


def _require_fragments(text: str, fragments: list[str]) -> None:
    normalized = text.lower()
    missing = [fragment for fragment in fragments if fragment.lower() not in normalized]
    if missing:
        snippet = " ".join(text.split())[:500]
        raise RuntimeError(f"missing fragments {missing}; answer was: {snippet}")


def _run_agent_with_retry(message: str, thread_id: str, attempts: int = 3) -> str:
    """Run a live agent query with short retries for provider rate limits."""
    from agent import run_agent

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return run_agent(message, thread_id=thread_id)
        except Exception as exc:
            last_error = exc
            error_text = str(exc).lower()
            if "tokens per day" in error_text or "tpd" in error_text:
                raise SkipCheck("Groq daily token quota is exhausted")
            if "rate limit" not in error_text or attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"agent query failed after retries: {last_error}")


def _thread_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4()}"


class SkipCheck(Exception):
    """Raised when an e2e check is not applicable on this machine."""


if __name__ == "__main__":
    raise SystemExit(main())
