"""Synthetic log corpus for training when DB has insufficient rows."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

from lstm_model import SEQ_LEN


def synthetic_normal_log(rng: random.Random) -> dict[str, Any]:
    port = rng.choice([80, 443, 22, 53, 21])
    proto = "UDP" if port == 53 else "TCP"
    et_map = {
        80: "http_request",
        443: "http_request",
        22: "ssh_login",
        53: "dns_query",
        21: "ftp_transfer",
    }
    bt = rng.randint(500, 40_000) if port != 53 else rng.randint(80, 400)
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "timestamp": ts,
        "source_ip": f"192.168.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
        "destination_ip": f"10.0.{rng.randint(0, 5)}.{rng.randint(1, 200)}",
        "destination_port": port,
        "protocol": proto,
        "event_type": et_map[port],
        "bytes_transferred": bt,
        "username": rng.choice([None, None, "svc_account"]),
        "raw_message": f"synthetic normal {port} len={bt}",
    }


def build_training_corpus(
    rng: random.Random,
) -> tuple[list[dict[str, Any]], list[list[dict[str, Any]]]]:
    logs = [synthetic_normal_log(rng) for _ in range(500)]
    sequences: list[list[dict[str, Any]]] = []
    for _ in range(250):
        src = f"10.{rng.randint(0, 50)}.{rng.randint(0, 255)}.{rng.randint(1, 200)}"
        seq = []
        for __ in range(SEQ_LEN):
            e = synthetic_normal_log(rng)
            e["source_ip"] = src
            seq.append(e)
        sequences.append(seq)
    return logs, sequences
