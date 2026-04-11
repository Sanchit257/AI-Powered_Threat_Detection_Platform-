"""Unit tests for detection pipeline: IsolationForest, features, MITRE pre-labels."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pytest

from features import log_dict_to_vector, vectorize_batch
from isolation_forest_model import IsolationForestDetector
from mitre_map import MITRE_ATTACK_MAP, prelabel_from_event_type


def synthetic_normal_log(rng: random.Random) -> dict[str, Any]:
    """Same distribution as ml_engine.main.synthetic_normal_log (no heavy imports)."""
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


@pytest.fixture
def trained_if() -> IsolationForestDetector:
    rng = random.Random(42)
    normals = [synthetic_normal_log(rng) for _ in range(400)]
    det = IsolationForestDetector()
    det.train(normals)
    return det


def test_isolation_forest_normal_below_five(trained_if: IsolationForestDetector) -> None:
    rng = random.Random(99)
    probe = synthetic_normal_log(rng)
    assert trained_if.score(probe) < 5.0


def test_isolation_forest_attack_above_six(trained_if: IsolationForestDetector) -> None:
    attack = {
        "timestamp": "2026-01-01T12:00:00Z",
        "source_ip": "192.168.1.1",
        "destination_ip": "10.0.0.1",
        "destination_port": 31337,
        "protocol": "TCP",
        "event_type": "port_scan",
        "bytes_transferred": 999_999_999,
        "username": None,
        "raw_message": "multi-port scan burst",
    }
    assert trained_if.score(attack) > 6.0


def test_feature_vector_shape() -> None:
    log = {
        "timestamp": "2026-01-01T12:00:00Z",
        "source_ip": "10.0.0.1",
        "destination_port": 443,
        "protocol": "TCP",
        "event_type": "http_request",
        "bytes_transferred": 1200,
        "username": None,
        "raw_message": "GET /",
    }
    v = log_dict_to_vector(log)
    assert v.shape == (8,)
    batch = vectorize_batch([log, log])
    assert batch.shape == (2, 8)


@pytest.mark.parametrize(
    "event_type,expected_tid",
    [
        ("port_scan", "T1046"),
        ("brute_force", "T1110"),
        ("data_exfil", "T1048"),
        ("ssh_login", "T1021"),
    ],
)
def test_mitre_map_event_types(event_type: str, expected_tid: str) -> None:
    pre = prelabel_from_event_type(event_type)
    assert pre["technique_id"] == expected_tid
    assert event_type in MITRE_ATTACK_MAP


def test_mitre_map_port_scan_tactic() -> None:
    pre = prelabel_from_event_type("port_scan")
    assert pre["mitre_tactic"] == "Reconnaissance"
    assert "T1046" in pre["mitre_technique"]
