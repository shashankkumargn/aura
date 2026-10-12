"""Output composer node: synthesize agent outputs and enforce DB grounding checks.

One job: assemble final omnichannel customer response and verify product/order grounding.
Allowed tools: none.
"""

from __future__ import annotations

import re
from typing import Any

from app.db.models import Order, Product
from app.db.session import SessionLocal
from app.state import AuraState


def _verify_grounding(text: str) -> str:
    """Verify that any cited product ID or order ID exists in the database; remove false citations."""
    db = SessionLocal()
    try:
        # Check Product IDs (e.g., P001, P042)
        prod_matches = set(re.findall(r"\b(P\d{3})\b", text, re.IGNORECASE))
        for p_id in prod_matches:
            exists = db.query(Product).filter(Product.id == p_id.upper()).first()
            if not exists:
                text = re.sub(rf"\b{p_id}\b", "", text)

        # Check Order IDs (e.g., ORD-1001)
        order_matches = set(re.findall(r"\b(ORD-[A-Za-z0-9]+)\b", text, re.IGNORECASE))
        for o_id in order_matches:
            exists = db.query(Order).filter(Order.id == o_id.upper()).first()
            if not exists:
                text = re.sub(rf"\b{o_id}\b", "your recent order", text)

        return re.sub(r"\s{2,}", " ", text).strip()
    finally:
        db.close()


def output_composer_node(state: AuraState) -> dict[str, Any]:
    """LangGraph terminal node: synthesize output or produce safe refusal."""
    policy_flags = state.get("policy_flags") or []
    if policy_flags:
        # Pre-written safe refusal
        refusal_reasons = "; ".join(policy_flags)
        safe_reply = (
            "I apologize, but I cannot fulfill this request due to our security and privacy policies. "
            f"Policy flag: {refusal_reasons}. Please contact customer support for further assistance."
        )
        return {"final_response": safe_reply}

    agent_outputs = state.get("agent_outputs") or {}
    channel = state.get("channel") or "web"

    response_parts: list[str] = []

    # 1. Sales
    if "sales" in agent_outputs:
        sales_val = agent_outputs["sales"]
        if isinstance(sales_val, dict):
            msg = sales_val.get("message")
            if msg:
                response_parts.append(msg)
        elif isinstance(sales_val, str):
            response_parts.append(sales_val)

    # 2. Recommendation
    if "recommendation" in agent_outputs:
        rec_val = agent_outputs["recommendation"]
        if isinstance(rec_val, dict):
            msg = rec_val.get("message")
            if msg:
                response_parts.append(msg)
        elif isinstance(rec_val, str):
            response_parts.append(rec_val)

    # 3. Inventory
    if "inventory" in agent_outputs:
        inv_val = agent_outputs["inventory"]
        if isinstance(inv_val, dict):
            msg = inv_val.get("message")
            if msg:
                response_parts.append(msg)
        elif isinstance(inv_val, str):
            response_parts.append(inv_val)

    # 4. Fulfillment
    if "fulfillment" in agent_outputs:
        ful_val = agent_outputs["fulfillment"]
        if isinstance(ful_val, dict):
            msg = ful_val.get("message")
            if msg:
                response_parts.append(msg)
        elif isinstance(ful_val, str):
            response_parts.append(ful_val)

    # 5. Payment
    if "payment" in agent_outputs:
        pay_val = agent_outputs["payment"]
        if isinstance(pay_val, dict):
            msg = pay_val.get("message")
            if msg:
                response_parts.append(msg)
        elif isinstance(pay_val, str):
            response_parts.append(pay_val)

    # 6. Loyalty
    if "loyalty" in agent_outputs:
        loy_val = agent_outputs["loyalty"]
        if isinstance(loy_val, dict):
            msg = loy_val.get("message")
            if msg:
                response_parts.append(msg)
        elif isinstance(loy_val, str):
            response_parts.append(loy_val)

    # 7. Post Purchase
    if "post_purchase" in agent_outputs:
        pp_val = agent_outputs["post_purchase"]
        if isinstance(pp_val, dict):
            msg = pp_val.get("message")
            if msg:
                response_parts.append(msg)
        elif isinstance(pp_val, str):
            response_parts.append(pp_val)

    if not response_parts:
        raw_reply = (
            "Hello! I am AURA, your Omnichannel Retail Assistant. "
            "How can I help you today with product searches, recommendations, order tracking, or returns?"
        )
    else:
        raw_reply = "\n\n".join(response_parts)

    # Omnichannel format adaptation
    if channel == "whatsapp_sim":
        header = "✨ *AURA Retail Assistant* ✨\n\n"
        final_text = header + raw_reply
    elif channel == "kiosk_sim":
        header = "📍 *AURA In-Store Kiosk*\n\n"
        final_text = header + raw_reply
    else:
        final_text = raw_reply

    # Run grounding verification against SQLite database
    grounded_text = _verify_grounding(final_text)

    return {"final_response": grounded_text}
