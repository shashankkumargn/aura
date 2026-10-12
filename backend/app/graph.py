"""Hierarchical multi-agent LangGraph StateGraph orchestration for AURA."""

from __future__ import annotations

from typing import Any, Literal
from langgraph.graph import END, START, StateGraph

from app.agents.coordinator import coordinator_node
from app.agents.fulfillment import fulfillment_node
from app.agents.inventory import inventory_node
from app.agents.loyalty import loyalty_node
from app.agents.output_composer import output_composer_node
from app.agents.payment import payment_node
from app.agents.planner import planner_node
from app.agents.post_purchase import post_purchase_node
from app.agents.recommendation import recommendation_node
from app.agents.sales import sales_node
from app.agents.supervisor import supervisor_node
from app.state import AuraState


def route_after_supervisor(
    state: AuraState,
) -> Literal[
    "output_composer",
    "planner",
    "sales",
    "inventory",
    "recommendation",
    "payment",
    "fulfillment",
    "loyalty",
    "post_purchase",
]:
    """Conditional router based on policy_flags, compound plan, and intent."""
    policy_flags = state.get("policy_flags") or []
    if policy_flags:
        return "output_composer"

    plan = state.get("plan")
    if plan and len(plan) > 1:
        return "planner"

    intent = (state.get("intent") or "general_faq").lower()

    if intent in ("product_search", "sales"):
        return "sales"
    if intent in ("inventory", "stock"):
        return "inventory"
    if intent in ("recommendation", "recommend"):
        return "recommendation"
    if intent in ("payment", "checkout"):
        return "payment"
    if intent in ("order_status", "fulfillment", "tracking"):
        return "fulfillment"
    if intent in ("loyalty", "points"):
        return "loyalty"
    if intent in ("return_or_complaint", "post_purchase", "returns", "warranty"):
        return "post_purchase"

    return "output_composer"


def execute_plan_node(state: AuraState) -> dict[str, Any]:
    """Execute each planned subtask sequentially and collect agent outputs."""
    plan = state.get("plan") or []
    current_state = dict(state)
    agent_outputs = dict(current_state.get("agent_outputs") or {})

    agent_node_map = {
        "sales": sales_node,
        "product_search": sales_node,
        "inventory": inventory_node,
        "recommendation": recommendation_node,
        "payment": payment_node,
        "fulfillment": fulfillment_node,
        "order_status": fulfillment_node,
        "loyalty": loyalty_node,
        "post_purchase": post_purchase_node,
        "return_or_complaint": post_purchase_node,
    }

    for step in plan:
        target_agent = str(step.get("agent", "")).lower()
        node_fn = agent_node_map.get(target_agent)
        if node_fn:
            step_state = dict(current_state)
            step_state["agent_outputs"] = agent_outputs
            step_res = node_fn(step_state)
            if "agent_outputs" in step_res:
                agent_outputs.update(step_res["agent_outputs"])

    return {"agent_outputs": agent_outputs}


# Construct StateGraph
builder: StateGraph = StateGraph(AuraState)

builder.add_node("coordinator", coordinator_node)
builder.add_node("supervisor", supervisor_node)
builder.add_node("planner", execute_plan_node)
builder.add_node("sales", sales_node)
builder.add_node("inventory", inventory_node)
builder.add_node("recommendation", recommendation_node)
builder.add_node("payment", payment_node)
builder.add_node("fulfillment", fulfillment_node)
builder.add_node("loyalty", loyalty_node)
builder.add_node("post_purchase", post_purchase_node)
builder.add_node("output_composer", output_composer_node)

builder.add_edge(START, "coordinator")
builder.add_edge("coordinator", "supervisor")

builder.add_conditional_edges(
    "supervisor",
    route_after_supervisor,
    {
        "output_composer": "output_composer",
        "planner": "planner",
        "sales": "sales",
        "inventory": "inventory",
        "recommendation": "recommendation",
        "payment": "payment",
        "fulfillment": "fulfillment",
        "loyalty": "loyalty",
        "post_purchase": "post_purchase",
    },
)

builder.add_edge("planner", "output_composer")
builder.add_edge("sales", "output_composer")
builder.add_edge("inventory", "output_composer")
builder.add_edge("recommendation", "output_composer")
builder.add_edge("payment", "output_composer")
builder.add_edge("fulfillment", "output_composer")
builder.add_edge("loyalty", "output_composer")
builder.add_edge("post_purchase", "output_composer")

builder.add_edge("output_composer", END)

graph = builder.compile()
