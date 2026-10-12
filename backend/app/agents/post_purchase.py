"""Post-purchase node: handle returns, refund tickets, and policy guidance.

One job: check return policy rules, verify return eligibility, and file return requests.
Allowed tools: submit_return_request, rag_search.
"""

from __future__ import annotations

import re
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.state import AuraState
from app.tools.order_tools import submit_return_request
from app.tools.rag_tools import rag_search

_TOOLS = [submit_return_request, rag_search]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

PP_SYSTEM_PROMPT = """You are the Post-Purchase Agent for AURA.
Your job is to assist customers with returns, refunds, warranty inquiries, and complaints.
- Call rag_search to retrieve return window and warranty policy terms from the store knowledge base.
- If the customer wants to return an item and has an order ID (e.g. ORD-1001), verify eligibility against the policy.
- If eligible, call submit_return_request to book the return and provide the ticket ID and pickup window.
- If ineligible (e.g., past the 14-day window), explain why politely citing the policy excerpt.
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


def post_purchase_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: manage returns and post-purchase policy support."""
    agent_outputs = dict(state.get("agent_outputs") or {})
    user_msg = _get_user_message(state)

    llm = get_llm(role="default")
    llm_with_tools = llm.bind_tools(_TOOLS)

    messages = [
        SystemMessage(content=PP_SYSTEM_PROMPT),
        HumanMessage(content=user_msg or "What is your return policy?"),
    ]

    first = llm_with_tools.invoke(messages)
    messages.append(first)

    pp_data: dict[str, Any] = {}
    tool_calls = getattr(first, "tool_calls", None) or []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        call_id = tc["id"]
        if name in _TOOLS_BY_NAME:
            result = _TOOLS_BY_NAME[name].invoke(args)
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            if isinstance(result, dict):
                pp_data = result

    if tool_calls:
        final = llm.invoke(messages)
        message_text = final.content
    else:
        # Fallback to direct return request if order ID detected
        match = re.search(r"ORD-[A-Za-z0-9]+", user_msg, re.IGNORECASE)
        order_id = match.group(0).upper() if match else "ORD-1001"
        if "return" in user_msg.lower():
            pp_data = submit_return_request.invoke({"order_id": order_id, "reason": "Customer return"})
            message_text = pp_data.get("message", "Return processed.")
        else:
            policy_chunks = rag_search.invoke({"query": "return policy"})
            message_text = policy_chunks[0] if policy_chunks else "AURA offers a 14-day hassle-free return window."
            pp_data = {"policy": message_text}

    return {
        "agent_outputs": {
            **agent_outputs,
            "post_purchase": {
                "message": message_text,
                "data": pp_data,
            },
        }
    }
