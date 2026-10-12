"""Fulfillment node: handle order tracking and shipment progression.

One job: answer 'where is my order' and track delivery progression.
Allowed tools: get_shipment_status_mock.
"""

from __future__ import annotations

import re
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.state import AuraState
from app.tools.order_tools import get_shipment_status_mock

_TOOLS = [get_shipment_status_mock]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

FULFILLMENT_SYSTEM_PROMPT = """You are the Fulfillment Agent for AURA.
Your job is to call get_shipment_status_mock to track customer deliveries.
- Answer questions like 'where is my order' with the current carrier, status (placed, packed, shipped, delivered), and estimated arrival.
- Always provide a polite, reassuring tone and explain next steps.
- If the tool cannot find the order, ask the customer to verify their order ID format (e.g. ORD-1001).
"""


def _get_user_message(state: AuraState) -> str:
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


def fulfillment_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: track orders and delivery progress."""
    agent_outputs = dict(state.get("agent_outputs") or {})
    user_msg = _get_user_message(state)

    llm = get_llm(role="default")
    llm_with_tools = llm.bind_tools(_TOOLS)

    messages = [
        SystemMessage(content=FULFILLMENT_SYSTEM_PROMPT),
        HumanMessage(content=user_msg or "Where is my order?"),
    ]

    first = llm_with_tools.invoke(messages)
    messages.append(first)

    shipment_res: dict[str, Any] = {}
    tool_calls = getattr(first, "tool_calls", None) or []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        call_id = tc["id"]
        if name in _TOOLS_BY_NAME:
            result = _TOOLS_BY_NAME[name].invoke(args)
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            if isinstance(result, dict):
                shipment_res = result

    if tool_calls:
        final = llm.invoke(messages)
        message_text = final.content
    else:
        # Fallback to customer's order ORD-1001 or extracted ID
        match = re.search(r"ORD-[A-Za-z0-9]+", user_msg, re.IGNORECASE)
        order_id = match.group(0).upper() if match else "ORD-1001"
        shipment_res = get_shipment_status_mock.invoke({"order_id": order_id})
        message_text = shipment_res.get("message", f"Tracking for {order_id} completed.")

    return {
        "agent_outputs": {
            **agent_outputs,
            "fulfillment": {
                "message": message_text,
                "data": shipment_res,
            },
        }
    }
