"""Payment node: handle checkout and simulated transaction processing.

One job: process simulated payments for customer orders.
Allowed tools: process_payment_mock.
"""

from __future__ import annotations

import re
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.state import AuraState
from app.tools.payment_tools import process_payment_mock

_TOOLS = [process_payment_mock]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

PAYMENT_SYSTEM_PROMPT = """You are the Payment Agent for AURA.
Your job is to call process_payment_mock to process payment for an order.
- Given an order_id and payment method, call the tool.
- Reply with a clear success or failure message, transaction ID, and order details.
- You MUST state plainly that this is a simulated payment for a Phase-1 prototype, never implying a real financial charge occurred.
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


def payment_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: simulate order payment."""
    agent_outputs = dict(state.get("agent_outputs") or {})
    user_msg = _get_user_message(state)

    llm = get_llm(role="default")
    llm_with_tools = llm.bind_tools(_TOOLS)

    messages = [
        SystemMessage(content=PAYMENT_SYSTEM_PROMPT),
        HumanMessage(content=user_msg or "Process payment for order."),
    ]

    first = llm_with_tools.invoke(messages)
    messages.append(first)

    pay_res: dict[str, Any] = {}
    tool_calls = getattr(first, "tool_calls", None) or []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        call_id = tc["id"]
        if name in _TOOLS_BY_NAME:
            result = _TOOLS_BY_NAME[name].invoke(args)
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            if isinstance(result, dict):
                pay_res = result

    if tool_calls:
        final = llm.invoke(messages)
        message_text = final.content
    else:
        # Fallback extraction of order ID
        match = re.search(r"ORD-[A-Za-z0-9]+", user_msg, re.IGNORECASE)
        order_id = match.group(0).upper() if match else "ORD-1001"
        pay_res = process_payment_mock.invoke({"order_id": order_id, "method": "UPI"})
        message_text = f"Simulated Phase-1 Payment: {pay_res.get('message')} (No real financial charge incurred)."

    return {
        "agent_outputs": {
            **agent_outputs,
            "payment": {
                "message": message_text,
                "data": pay_res,
            },
        }
    }
