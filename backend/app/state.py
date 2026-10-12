"""Shared AuraState schema passed between all LangGraph nodes."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AuraState(TypedDict):
    """Conversation and routing state shared across the AURA agent graph."""

    session_id: str
    channel: str
    user_id: str
    messages: Annotated[list, add_messages]
    intent: str | None
    max_price: int | None
    plan: list[dict] | None
    agent_outputs: dict
    retrieved_context: list[str]
    policy_flags: list[str]
    final_response: str | None
