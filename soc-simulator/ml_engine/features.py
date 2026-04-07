"""Feature engineering: raw log dict -> (8,) float32 vector."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np

COMMON_PORTS = {80, 443, 22, 53, 21, 25, 3306, 5432}

EVENT_TYPE_ORDER = [
    "http_request",
    "dns_query",
    "ssh_login",
    "ftp_transfer",
    "port_scan",
    "brute_force",
    "data_exfil",
    "other",
]


def _parse_ts(ts: str) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    s = ts.replace("Z", "+00:00") if ts.endswith("Z") else ts
    return datetime.fromisoformat(s)


def log_dict_to_vector(log: Mapping[str, Any]) -> np.ndarray:
    """
    Features (8):
    0. destination_port / 65535
    1. log1p(bytes) / log1p(1e9) (bounded log-scale)
    2. is_common_port
    3. protocol encoded: TCP=0, UDP=1, ICMP=2 -> normalized /2
    4. hour_of_day (continuous hour/24)
    5. is_weekend
    6. event_type encoded -> normalized index
    7. has_username
    """
    port = log.get("destination_port")
    port_f = float(port) / 65535.0 if port is not None else 0.0

    bt = int(log.get("bytes_transferred") or 0)
    log_bytes = math.log1p(max(bt, 0)) / math.log1p(1e9)
    log_bytes = min(1.0, log_bytes)

    p = int(port) if port is not None else -1
    is_common = 1.0 if p in COMMON_PORTS else 0.0

    proto = (log.get("protocol") or "TCP").upper()
    if proto == "TCP":
        pe = 0.0
    elif proto == "UDP":
        pe = 1.0
    elif proto == "ICMP":
        pe = 2.0
    else:
        pe = 0.0
    pe_norm = pe / 2.0

    dt = _parse_ts(str(log.get("timestamp") or ""))
    hour = dt.hour + dt.minute / 60.0
    hour_norm = hour / 24.0
    weekend = 1.0 if dt.weekday() >= 5 else 0.0

    et = str(log.get("event_type") or "other")
    if et in EVENT_TYPE_ORDER:
        et_idx = EVENT_TYPE_ORDER.index(et)
    else:
        et_idx = EVENT_TYPE_ORDER.index("other")
    et_norm = et_idx / max(1, len(EVENT_TYPE_ORDER) - 1)

    uname = log.get("username")
    has_user = 1.0 if uname not in (None, "", "null") else 0.0

    return np.array(
        [port_f, log_bytes, is_common, pe_norm, hour_norm, weekend, et_norm, has_user],
        dtype=np.float32,
    )


def vectorize_batch(logs: list[Mapping[str, Any]]) -> np.ndarray:
    if not logs:
        return np.zeros((0, 8), dtype=np.float32)
    return np.stack([log_dict_to_vector(x) for x in logs], axis=0)
