"""Optional Slack incoming webhook for CRITICAL alerts (severity >= 9)."""

from __future__ import annotations

import os
from typing import Any

STATS_CACHE_KEY = "soc:stats:v1"


def notify_slack_if_critical(row: dict[str, Any], redis_client: Any | None) -> None:
    try:
        sev = int(row.get("severity") or 0)
    except (TypeError, ValueError):
        sev = 0
    if sev < 9:
        return

    if redis_client is not None:
        try:
            redis_client.delete(STATS_CACHE_KEY)
        except Exception:
            pass

    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        return

    try:
        import httpx

        et = row.get("event_type") or "unknown"
        sip = row.get("source_ip") or "—"
        tactic = row.get("mitre_tactic") or "—"
        text = (
            f"CRITICAL ALERT: {et} from {sip} — {tactic} — Score: {sev}/10"
        )
        httpx.post(url, json={"text": text}, timeout=10.0)
    except Exception:
        pass
