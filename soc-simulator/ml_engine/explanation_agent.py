"""LLM explanations for alerts via Anthropic Claude."""

from __future__ import annotations

import json
import os
import re
from typing import Any

SYSTEM_PROMPT = (
    "You are a cybersecurity analyst. Given a network anomaly, "
    "identify the attack type, map it to MITRE ATT&CK framework, and explain "
    "what the attacker is attempting. Respond in JSON only."
)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def get_explanation(alert_context: dict) -> dict:
    """
    Returns dict with keys: mitre_tactic, mitre_technique, explanation.
    On failure, empty strings.
    """
    empty = {"mitre_tactic": "", "mitre_technique": "", "explanation": ""}
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return empty

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        user_msg = json.dumps(alert_context, default=str)
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
        if not parsed:
            return empty
        return {
            "mitre_tactic": str(parsed.get("mitre_tactic", "") or ""),
            "mitre_technique": str(parsed.get("mitre_technique", "") or ""),
            "explanation": str(parsed.get("explanation", "") or ""),
        }
    except Exception:
        return empty
