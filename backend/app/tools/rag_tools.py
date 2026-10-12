"""Retail policy and knowledge retrieval tools for AURA."""

from __future__ import annotations

from typing import Any
from langchain_core.tools import tool

from app.memory.vector_store import search


@tool
def rag_search(query: str) -> list[str]:
    """Search retail knowledge base for store policies (returns, warranties, shipping, loyalty) and product descriptions; returns list[str] of matching excerpts."""
    return search(query=query, k=4)


def get_return_policy(query: str = "") -> dict[str, Any]:
    """Retrieve retail store policies on returns, cancellations, and warranties; returns dict(policy_category=str, window_days=int, conditions=list[str], refund_method=str, message=str)."""
    excerpts = search(query=query or "return policy", k=2)
    message = excerpts[0] if excerpts else "AURA offers a 14-day hassle-free return window."
    return {
        "policy_category": "Returns & Replacements",
        "window_days": 14,
        "conditions": [
            "Item must be in unused condition with original tags intact.",
            "Electronics must include all accessories.",
        ],
        "refund_method": "Original payment method within 5-7 business days.",
        "message": message,
    }
