"""Recommendation node: suggest products tailored to customer preferences.

One job: provide personalized product recommendations and preserve explainability rationale.
Allowed tools: get_recommendations.
"""

from __future__ import annotations

from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from app.llm import get_llm
from app.ml.recommender import get_recommendations
from app.state import AuraState

_TOOLS = [get_recommendations]
_TOOLS_BY_NAME = {t.name: t for t in _TOOLS}

REC_SYSTEM_PROMPT = """You are the Recommendation Agent for AURA.
Your job is to call get_recommendations and present personalized recommendations to the customer.
- Always cite the product name, price, and the specific 'why' rationale from the tool output.
- Present the recommendations in a clear, friendly, and structured manner (2-4 sentences or bullet points).
- Never invent product details not present in the tool results.
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
    return "Recommend some great products for me."


def recommendation_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: generate explainable product recommendations."""
    agent_outputs = dict(state.get("agent_outputs") or {})
    user_id = state.get("user_id") or "u123"
    user_msg = _get_user_message(state)

    llm = get_llm(role="default")
    llm_with_tools = llm.bind_tools(_TOOLS)

    messages = [
        SystemMessage(content=REC_SYSTEM_PROMPT),
        HumanMessage(content=f"User ID: {user_id}. Request: {user_msg}"),
    ]

    first = llm_with_tools.invoke(messages)
    messages.append(first)

    raw_recommendations: list[dict[str, Any]] = []
    tool_calls = getattr(first, "tool_calls", None) or []
    for tc in tool_calls:
        name = tc["name"]
        args = tc["args"]
        call_id = tc["id"]
        if name in _TOOLS_BY_NAME:
            result = _TOOLS_BY_NAME[name].invoke(args)
            messages.append(ToolMessage(content=str(result), tool_call_id=call_id))
            if isinstance(result, list):
                raw_recommendations.extend(result)

    if tool_calls:
        final = llm.invoke(messages)
        message_text = final.content
    else:
        # If model didn't call tool automatically, invoke deterministically
        raw_recommendations = get_recommendations.invoke({"user_id": user_id, "k": 4})
        items_str = "\n".join(f"- **{r['name']}** (₹{r['price']:,}) — *{r['why']}*" for r in raw_recommendations)
        message_text = f"Here are personalized recommendations based on your store profile:\n{items_str}"

    return {
        "agent_outputs": {
            **agent_outputs,
            "recommendation": {
                "message": message_text,
                "recommendations": raw_recommendations,
            },
        }
    }
