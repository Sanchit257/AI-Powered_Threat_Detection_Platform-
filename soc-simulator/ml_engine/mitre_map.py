"""Rule-based MITRE ATT&CK pre-labels by event_type (no LLM)."""

from __future__ import annotations

from typing import Any, TypedDict


class MitrePrelabel(TypedDict):
    mitre_tactic: str
    mitre_technique: str
    technique_id: str
    confidence: float


MITRE_ATTACK_MAP: dict[str, MitrePrelabel] = {
    "port_scan": {
        "mitre_tactic": "Reconnaissance",
        "mitre_technique": "T1046 - Network Service Discovery",
        "technique_id": "T1046",
        "confidence": 0.72,
    },
    "brute_force": {
        "mitre_tactic": "Credential Access",
        "mitre_technique": "T1110 - Brute Force",
        "technique_id": "T1110",
        "confidence": 0.75,
    },
    "data_exfil": {
        "mitre_tactic": "Exfiltration",
        "mitre_technique": "T1048 - Exfiltration Over Alternative Protocol",
        "technique_id": "T1048",
        "confidence": 0.7,
    },
    "ssh_login": {
        "mitre_tactic": "Lateral Movement",
        "mitre_technique": "T1021 - Remote Services",
        "technique_id": "T1021",
        "confidence": 0.65,
    },
}


def prelabel_from_event_type(event_type: str | None) -> MitrePrelabel:
    key = (event_type or "").strip().lower()
    if key in MITRE_ATTACK_MAP:
        return MITRE_ATTACK_MAP[key]
    return {
        "mitre_tactic": "",
        "mitre_technique": "",
        "technique_id": "",
        "confidence": 0.0,
    }


def enrich_context_with_prelabel(alert_context: dict[str, Any]) -> dict[str, Any]:
    log = alert_context.get("log") or {}
    et = log.get("event_type") if isinstance(log, dict) else None
    pre = prelabel_from_event_type(str(et) if et is not None else None)
    out = dict(alert_context)
    out["rule_based_mitre"] = dict(pre)
    return out
