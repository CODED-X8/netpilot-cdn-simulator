"""Guardrails for NetPilot AI Copilot: Rate limiter, token budget, and kill switch."""

import os
import time
import math
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional


# Global in-memory state
_SESSION_REQUEST_TIMESTAMPS: Dict[str, List[float]] = {}
_DAILY_TOKEN_USAGE: Dict[str, int] = {}  # "YYYY-MM-DD" -> tokens count


def is_copilot_enabled() -> bool:
    """Check if NetPilot Copilot is enabled via COPILOT_ENABLED env var."""
    val = os.environ.get("COPILOT_ENABLED", "true").strip().lower()
    return val not in ("false", "0", "no", "off", "disable", "disabled")


def check_rate_limit(session_id: str) -> Tuple[bool, Optional[int]]:
    """Check sliding 60-second window rate limit for session.

    Returns:
        (allowed: bool, retry_after_seconds: Optional[int])
    """
    try:
        limit = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "10"))
    except ValueError:
        limit = 10

    if limit <= 0:
        return True, None

    now = time.time()
    cutoff = now - 60.0

    timestamps = _SESSION_REQUEST_TIMESTAMPS.setdefault(session_id, [])
    # Prune timestamps older than 60s
    valid_timestamps = [t for t in timestamps if t > cutoff]
    _SESSION_REQUEST_TIMESTAMPS[session_id] = valid_timestamps

    if len(valid_timestamps) >= limit:
        oldest = valid_timestamps[0]
        retry_after = max(1, int(math.ceil(60.0 - (now - oldest))))
        return False, retry_after

    valid_timestamps.append(now)
    return True, None


def get_daily_token_usage() -> Tuple[int, int]:
    """Retrieve current day's token usage and configured budget."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    current_used = _DAILY_TOKEN_USAGE.get(today, 0)
    try:
        budget = int(os.environ.get("DAILY_TOKEN_BUDGET", "100000"))
    except ValueError:
        budget = 100000
    return current_used, budget


def check_daily_token_budget() -> Tuple[bool, int, int]:
    """Check if daily token budget has been exhausted.

    Returns:
        (allowed: bool, current_used: int, budget: int)
    """
    current_used, budget = get_daily_token_usage()
    if budget <= 0:
        return True, current_used, budget

    if current_used >= budget:
        return False, current_used, budget
    return True, current_used, budget


def record_tokens_consumed(tokens: int) -> None:
    """Record token consumption against today's budget."""
    if tokens <= 0:
        return
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _DAILY_TOKEN_USAGE[today] = _DAILY_TOKEN_USAGE.get(today, 0) + tokens


def reset_guardrails() -> None:
    """Reset all guardrail memory (primarily for unit tests)."""
    global _SESSION_REQUEST_TIMESTAMPS, _DAILY_TOKEN_USAGE
    _SESSION_REQUEST_TIMESTAMPS.clear()
    _DAILY_TOKEN_USAGE.clear()
