"""Coordinator node: classify customer message into structured intent.

One job: entry-point understanding before routing continues.
Allowed tools: none.
"""

from __future__ import annotations

from typing import Any, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.llm import get_llm
from app.state import AuraState

SupportedIntent = Literal[
    "product_search",
    "recommendation",
    "inventory",
    "order_status",
    "payment",
    "loyalty",
    "return_or_complaint",
    "general_faq",
]

COORDINATOR_SYSTEM_PROMPT = """\
You are the Coordinator for AURA (Agentic Unified Retail Assistant for Omni-Channel Commerce).
Your job is ONLY to classify the customer's message into structured intent and confidence.
Do NOT answer the customer. Do NOT invent product catalogs or order data.

Choose exactly ONE intent from:
- product_search: search/browse products, check prices, filter catalog
- recommendation: recommendations, comparison between products, suggestions
- inventory: stock and availability checks ("is X in stock?")
- order_status: delivery, tracking, "where is my order?"
- payment: checkout, payment links, payment methods
- loyalty: reward points balance, points redemption, tier status
- return_or_complaint: returns, cancellations, refunds, warranties, damaged items
- general_faq: greetings, chitchat, help, store policies

Provide a confidence score between 0.0 and 1.0.
Set requires_planner=true if the request requires multiple sequential operations (e.g. "search for shoes and check order status").
"""


class CoordinatorResult(BaseModel):
    """Structured Coordinator output for downstream routing."""

    intent: SupportedIntent
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    reasoning: str = ""
    entities: dict[str, Any] = Field(default_factory=dict)
    requires_planner: bool = False


def coordinate(message: str) -> CoordinatorResult:
    """Classify a customer message using get_llm(role='router')."""
    text = (message or "").strip()
    if not text:
        return CoordinatorResult(
            intent="general_faq",
            confidence=1.0,
            reasoning="Empty input message.",
        )

    llm = get_llm(role="router").with_structured_output(CoordinatorResult)
    result = llm.invoke([
        SystemMessage(content=COORDINATOR_SYSTEM_PROMPT),
        HumanMessage(content=text),
    ])
    if not isinstance(result, CoordinatorResult):
        raise TypeError(f"Expected CoordinatorResult, got {type(result)!r}")
    return result


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


def coordinator_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: classify latest message and store intent in state."""
    text = _latest_user_text(state)
    if not text:
        return {"intent": "general_faq"}

    res = coordinate(text)
    return {
        "intent": res.intent,
        "plan": [{"agent": res.intent, "instruction": text}] if not res.requires_planner else None,
    }
