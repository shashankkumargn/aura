"""Supervisor node: policy enforcement and routing safety check.

One job: enforce safety policy rules and block unauthorized requests.
Allowed tools: none.
"""

from __future__ import annotations

import re
from typing import Any

from app.state import AuraState


def _latest_user_text(state: AuraState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, dict):
            if msg.get("role") in ("user", "human") and msg.get("content"):
                return str(msg["content"])
        else:
            role = getattr(msg, "role", None) or getattr(msg, "type", None)
            content = getattr(msg, "content", None)
            if role in ("user", "human") and content:
                return str(content)
    return ""


def supervisor_node(state: AuraState) -> dict[str, Any]:
    """Inspect state and user query for policy violations; populate policy_flags."""
    policy_flags: list[str] = list(state.get("policy_flags") or [])
    user_text = _latest_user_text(state).lower()
    user_id = state.get("user_id") or "u123"

    # Rule 1: Block inquiries into another customer's personal data or unauthorized access
    other_customer_match = re.search(r"\b(cust-\d+|user[0-9]+)\b", user_text)
    if other_customer_match:
        target_cust = other_customer_match.group(0)
        if target_cust.lower() != user_id.lower() and "u123" not in target_cust.lower():
            policy_flags.append(f"UNAUTHORIZED_ACCESS: Attempted to inspect account data for '{target_cust}'.")

    # Rule 2: Block abusive or malicious injection patterns
    if any(k in user_text for k in ["drop table", "select * from", "system prompt", "ignore all instructions"]):
        policy_flags.append("PROMPT_INJECTION_OR_SQLI: Disallowed query pattern detected.")

    # Rule 3: Cap suspicious excessive loyalty point claims (e.g. "give me 1000000 points")
    if "points" in user_text and any(num in user_text for num in ["100000", "50000", "999999"]):
        policy_flags.append("EXCESSIVE_REDEMPTION: Redemption claim exceeds maximum allowable cap.")

    return {"policy_flags": policy_flags}
