"""Spending protection for the live demo (owner rule, Oct 4).

- Daily cap (`daily_budget_usd`): when today's measured spend reaches it, answers fall back
  from the main model to the cheaper fallback model.
- Hard stop (`hard_budget_usd`): above it no model is called; the API returns search passages
  only (never a broken page).
- 80% warning: logged and exposed at /health so the owner sees it.
- Per-IP rate limit on /answer for non-cached answers.
Spend is measured from the usage log (provider-reported cost per call).
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import UTC, datetime

from api.llm import USAGE_LOG
from api.settings import settings

_lock = threading.Lock()
_hits: dict[str, deque] = {}


SERVING_STAGES = ("classify", "answer", "embed/query")


def spend(
    since_ts: float = 0.0, provider: str | None = "openrouter", serving_only: bool = False
) -> float:
    total = 0.0
    if not USAGE_LOG.exists():
        return 0.0
    for line in USAGE_LOG.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("cached") or r["ts"] < since_ts:
            continue
        if provider and r.get("provider") != provider:
            continue
        if serving_only and not r["stage"].startswith(SERVING_STAGES):
            continue
        total += float(r.get("cost_usd") or 0.0)
    return total


def today_start() -> float:
    now = datetime.now(UTC)
    return datetime(now.year, now.month, now.day, tzinfo=UTC).timestamp()


_remote: dict = {"ts": 0.0, "usage": None}


def _openrouter_usage() -> float | None:
    """Authoritative total spend from OpenRouter (survives server restarts and redeploys,
    unlike the local log on an ephemeral disk). Cached for 60 s; None if unreachable."""
    import httpx

    if time.time() - _remote["ts"] < 60:
        return _remote["usage"]
    try:
        r = httpx.get(
            "https://openrouter.ai/api/v1/key",
            timeout=5,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        )
        _remote["usage"] = float(r.json()["data"]["usage"]) if r.status_code == 200 else None
    except Exception:
        _remote["usage"] = None
    _remote["ts"] = time.time()
    return _remote["usage"]


def status() -> dict:
    today = spend(today_start(), serving_only=True)  # the daily cap is for live answering
    local_total = spend(0.0) + settings.openrouter_spend_offset_usd
    remote = _openrouter_usage() if settings.openrouter_api_key else None
    total = max(local_total, remote) if remote is not None else local_total
    budget = settings.openrouter_budget_usd
    return {
        "today_usd": round(today, 4),
        "daily_cap_usd": settings.daily_budget_usd,
        "total_usd": round(total, 4),
        "budget_usd": budget,
        "used_pct": round(100 * total / budget, 1) if budget else None,
        "warning": total >= 0.8 * budget,
        "hard_stop": total >= settings.hard_budget_usd,
        "source": "openrouter" if remote is not None else "local log",
    }


def answer_model() -> str | None:
    """Main model, fallback model under the daily cap, or None (passages only)."""
    s = status()
    if s["hard_stop"]:
        return None
    if s["today_usd"] >= settings.daily_budget_usd:
        return settings.answer_fallback_model
    return settings.answer_model


def allow(ip: str) -> bool:
    """Sliding one-hour window per IP for non-cached answers."""
    now = time.time()
    with _lock:
        q = _hits.setdefault(ip, deque())
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= settings.answer_rate_limit_per_hour:
            return False
        q.append(now)
        return True
