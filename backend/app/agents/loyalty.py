"""Loyalty node: handle reward points, balance lookups, and redemptions.

One job: look up loyalty points, explain tier benefits via policy RAG, and redeem points.
Allowed tools: get_loyalty_balance, redeem_points, rag_search.
"""

from __future__ import annotations

import re
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.state import AuraState
from app.tools.loyalty_tools import get_loyalty_balance, redeem_points
from app.tools.rag_tools import rag_search

_TOOLS = [get_loyalty_balance, redeem_points, rag_search]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

LOYALTY_SYSTEM_PROMPT = """You are the Loyalty Agent for AURA.
Your job is to assist with reward points balance inquiries and redemptions.
- Call get_loyalty_balance to look up current points and tier.
- Call redeem_points if the user explicitly wants to redeem points for an order discount.
- Pull tier benefit rules and program details from policies.json by calling rag_search rather than guessing or hardcoding them.
- If a redemption request exceeds the customer's balance, politely decline and state their available balance (a normal conversational refusal).
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


def loyalty_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: loyalty inquiries, tier benefits, and redemptions."""
    agent_outputs = dict(state.get("agent_outputs") or {})
    user_id = state.get("user_id") or "u123"
    user_msg = _get_user_message(state)

    llm = get_llm(role="default")
    llm_with_tools = llm.bind_tools(_TOOLS)

    messages = [
        SystemMessage(content=LOYALTY_SYSTEM_PROMPT),
        HumanMessage(content=f"User ID: {user_id}. Request: {user_msg or 'Check my loyalty balance'}"),
    ]

    first = llm_with_tools.invoke(messages)
    messages.append(first)

    loyalty_data: dict[str, Any] = {}
    tool_calls = getattr(first, "tool_calls", None) or []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        call_id = tc["id"]
        if name in _TOOLS_BY_NAME:
            result = _TOOLS_BY_NAME[name].invoke(args)
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            if isinstance(result, dict):
                loyalty_data = result

    if tool_calls:
        final = llm.invoke(messages)
        message_text = final.content
    else:
        # Fallback to direct tool call
        if "redeem" in user_msg.lower():
            match = re.search(r"(\d+)", user_msg)
            pts = int(match.group(1)) if match else 100
            loyalty_data = redeem_points.invoke({"user_id": user_id, "points": pts})
        else:
            loyalty_data = get_loyalty_balance.invoke({"user_id": user_id})
        message_text = loyalty_data.get("message", "Loyalty balance retrieved.")

    return {
        "agent_outputs": {
            **agent_outputs,
            "loyalty": {
                "message": message_text,
                "data": loyalty_data,
            },
        }
    }
