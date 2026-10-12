
"""Planner node: break multi-part customer requests into ordered subtasks.

One job: decompose complex retail requests into an execution plan.
Allowed tools: none.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.llm import get_llm
from app.state import AuraState


class PlanStep(BaseModel):
    step: int = Field(description="Step number")
    agent: str = Field(description="AURA agent responsible for this step")
    instruction: str = Field(description="What the agent should do")


class PlannerResult(BaseModel):
    steps: list[PlanStep]


PLANNER_SYSTEM_PROMPT = """
You are the Planner Agent of AURA
(Agentic Unified Retail Assistant for Omni-Channel Commerce).

Your job is to break a complex customer request into ordered,
actionable steps for AURA's specialized agents.

Available agents:
- sales: product search, pricing, product information
- recommendation: compare products and recommend products
- inventory: check product availability
- payment: payment-related operations
- fulfillment: delivery and order tracking
- loyalty: loyalty points and rewards
- post_purchase: returns, refunds, warranty and complaints

Only create multiple steps when the request actually requires
multiple operations.

Return a clear ordered execution plan.
"""


def create_plan(user_message: str) -> PlannerResult:
    """Invoke the LLM to generate an ordered list of agent subtasks."""
    text = user_message.strip()
    if not text:
        return PlannerResult(steps=[])

    llm = get_llm()
    structured_llm = llm.with_structured_output(PlannerResult)

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ]

    result = structured_llm.invoke(messages)
    if not isinstance(result, PlannerResult):
        raise TypeError(f"Expected PlannerResult, got {type(result)!r}")
    return result


def _latest_user_text(state: AuraState) -> str:
    """Extract latest user message content from state."""
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, dict):
            role = msg.get("role") or msg.get("type")
            content = msg.get("content", "")
            if role in ("user", "human") and content:
                return str(content)
            continue
        msg_type = getattr(msg, "type", None)
        content = getattr(msg, "content", None)
        if msg_type in ("human", "user") and content:
            return str(content)
    return ""


def planner_node(state: AuraState) -> dict[str, Any]:
    """LangGraph node: decompose the current user request into an execution plan."""
    user_text = _latest_user_text(state)
    if not user_text:
        return {"plan": []}

    try:
        plan_result = create_plan(user_text)
        return {"plan": [step.model_dump() for step in plan_result.steps]}
    except Exception as exc:
        # Fallback single-step plan if LLM is unavailable or fails
        fallback_agent = state.get("intent") or "sales"
        if fallback_agent in ("general", "unclassified"):
            fallback_agent = "sales"
        return {
            "plan": [
                {
                    "step": 1,
                    "agent": fallback_agent,
                    "instruction": f"Process request: {user_text} (fallback: {exc})",
                }
            ]
        }

