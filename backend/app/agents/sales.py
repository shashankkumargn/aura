"""Sales node: handle sales and product assistance tasks.

Allowed tools: search_products, rag_search.
"""

from __future__ import annotations

import sys
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from app.llm import get_llm
from app.state import AuraState
from app.tools.product_tools import search_products

# Ensure UTF-8 stdout encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure") and sys.stdout:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

search_products = tool(search_products) if not hasattr(search_products, "name") else search_products

# TODO: add rag_search when app/tools/rag_tools.py exists
_TOOLS = [search_products]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

SYSTEM_PROMPT = """You are the Sales assistant for AURA (Agentic Unified Retail Assistant).
- You may ONLY call: search_products, rag_search.
- NEVER quote a price, stock number, or product name that did not come back from a tool call in THIS turn.
- If search_products returns nothing, say so honestly — do not invent a product.
- If the user mentions a price cap ("under 2000"), pass it as max_price.
- If the user asks a policy question (returns, warranty), call rag_search.
- Reply in 1-3 sentences. Cite exact product names and prices from the tool output."""


def _get_user_message(state: AuraState) -> str | None:
    """Walk messages in reverse and return the text of the first user message."""
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
    return None


def sales_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: handle sales and product assistance via LLM tool-calling."""
    user_msg = _get_user_message(state)
    if not user_msg:
        return {"agent_outputs": {"sales": {"message": "No user message."}}}

    llm = get_llm(role="default")

    llm_with_tools = llm.bind_tools(_TOOLS)
    messages: list[Any] = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ]

    first = llm_with_tools.invoke(messages)
    messages.append(first)

    cited_products: list[dict[str, Any]] = []
    tool_calls = getattr(first, "tool_calls", None) or []
    for tool_call in tool_calls:
        name = tool_call["name"]
        args = tool_call["args"]
        call_id = tool_call["id"]
        if name in _TOOLS_BY_NAME:
            result = _TOOLS_BY_NAME[name].invoke(args)
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            if name == "search_products" and isinstance(result, list):
                cited_products.extend(result)

    if tool_calls:
        final = llm.invoke(messages)
    else:
        final = first

    return {
        "agent_outputs": {
            "sales": {
                "message": final.content,
                "cited_products": cited_products,
            }
        }
    }