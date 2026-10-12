"""Inventory node: check stock levels and product availability.

One job: query and report stock availability for requested products.
Allowed tools: check_stock.
"""

from __future__ import annotations

import os
import re
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.state import AuraState
from app.tools.inventory_tools import check_stock

_TOOLS = [check_stock]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "5"))

INV_SYSTEM_PROMPT = f"""You are the Inventory Agent for AURA.
Your job is to call check_stock to check product availability.
- Answer whether the item is in stock and how many units are left plainly.
- If the item's stock is at or below {LOW_STOCK_THRESHOLD} units, add a note that the item is low in stock.
- Never invent a stock number or product that was not returned by check_stock.
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


def inventory_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: check stock and report availability."""
    agent_outputs = dict(state.get("agent_outputs") or {})
    user_msg = _get_user_message(state)

    llm = get_llm(role="default")
    llm_with_tools = llm.bind_tools(_TOOLS)

    messages = [
        SystemMessage(content=INV_SYSTEM_PROMPT),
        HumanMessage(content=user_msg or "Check stock availability."),
    ]

    first = llm_with_tools.invoke(messages)
    messages.append(first)

    inventory_result: dict[str, Any] = {}
    tool_calls = getattr(first, "tool_calls", None) or []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        call_id = tc["id"]
        if name in _TOOLS_BY_NAME:
            result = _TOOLS_BY_NAME[name].invoke(args)
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            if isinstance(result, dict):
                inventory_result = result

    if tool_calls:
        final = llm.invoke(messages)
        message_text = final.content
    else:
        # Fallback keyword lookup if tool was not called directly
        match = re.search(r"(?:is|check|for)\s+([A-Za-z0-9\s]+?)(?:\s+in stock|\s+available|\?|$)", user_msg, re.IGNORECASE)
        query = match.group(1).strip() if match else user_msg
        inventory_result = check_stock.invoke({"product_id": query})
        message_text = inventory_result.get("message", "Stock check completed.")

    return {
        "agent_outputs": {
            **agent_outputs,
            "inventory": {
                "message": message_text,
                "data": inventory_result,
            },
        }
    }
