"""LLM explanations for alerts via Anthropic Claude + rule-based MITRE pre-labels."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from mitre_map import enrich_context_with_prelabel, prelabel_from_event_type

EXPLANATION_SCHEMA: dict[str, str] = {
    "mitre_tactic": "string, e.g. Credential Access",
    "mitre_technique": "string, e.g. T1110 - Brute Force",
    "technique_id": "string, e.g. T1110",
    "confidence": "float 0.0-1.0",
    "explanation": "2-3 sentence plain English",
    "recommended_action": "one sentence",
}

SYSTEM_PROMPT = f"""You are a cybersecurity analyst. Given network anomaly context (including optional rule_based_mitre hints), enrich the assessment.

Respond with a single JSON object ONLY, no markdown, matching exactly these keys:
{json.dumps(EXPLANATION_SCHEMA, indent=2)}

Rules:
- Prefer the rule_based_mitre tactic/technique/technique_id when they are non-empty unless evidence clearly contradicts them.
- Set confidence between 0 and 1 reflecting how well the mapping fits this specific log.
- explanation: 2-3 clear sentences for a SOC analyst.
- recommended_action: one imperative sentence (contain, investigate, block, etc.).
"""


def _empty_out() -> dict[str, Any]:
    return {
        "mitre_tactic": "",
        "mitre_technique": "",
        "technique_id": "",
        "confidence": 0.0,
        "explanation": "",
        "recommended_action": "",
    }


def _clamp_confidence(v: Any) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, x))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def _merge_pre_and_llm(pre: dict[str, Any], llm: dict[str, Any] | None) -> dict[str, Any]:
    if not llm:
        return {
            "mitre_tactic": pre.get("mitre_tactic", "") or "",
            "mitre_technique": pre.get("mitre_technique", "") or "",
            "technique_id": pre.get("technique_id", "") or "",
            "confidence": _clamp_confidence(pre.get("confidence", 0.0)),
            "explanation": "",
            "recommended_action": "Review the alert in the SIEM and correlate with adjacent events for this source.",
        }

    def pick_str(key: str, fallback: str) -> str:
        v = llm.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
        return fallback

    tactic = pick_str("mitre_tactic", pre.get("mitre_tactic", "") or "")
    technique = pick_str("mitre_technique", pre.get("mitre_technique", "") or "")
    tid = pick_str("technique_id", pre.get("technique_id", "") or "")
    conf = _clamp_confidence(llm.get("confidence", pre.get("confidence", 0.0)))
    expl = pick_str("explanation", "")
    action = pick_str(
        "recommended_action",
        "Escalate if impact is confirmed; otherwise monitor and tune detection thresholds.",
    )
    return {
        "mitre_tactic": tactic,
        "mitre_technique": technique,
        "technique_id": tid,
        "confidence": conf,
        "explanation": expl,
        "recommended_action": action,
    }


def get_explanation(alert_context: dict) -> dict[str, Any]:
    """
    Rule-based MITRE pre-label, then Claude enrichment. Returns merged dict with:
    mitre_tactic, mitre_technique, technique_id, confidence, explanation, recommended_action.
    """
    log = alert_context.get("log") or {}
    et = log.get("event_type") if isinstance(log, dict) else None
    pre = prelabel_from_event_type(str(et) if et is not None else None)
    pre_full = {
        "mitre_tactic": pre["mitre_tactic"],
        "mitre_technique": pre["mitre_technique"],
        "technique_id": pre["technique_id"],
        "confidence": pre["confidence"],
    }

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return _merge_pre_and_llm(pre_full, None)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        enriched_ctx = enrich_context_with_prelabel(alert_context)
        user_msg = json.dumps(enriched_ctx, default=str)
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        text = ""
        for block in msg.content:
            if hasattr(block, "text"):
                text += block.text
            elif isinstance(block, dict) and "text" in block:
                text += block["text"]
        parsed = _extract_json_object(text)
        return _merge_pre_and_llm(pre_full, parsed)
    except Exception:
        return _merge_pre_and_llm(pre_full, None)
