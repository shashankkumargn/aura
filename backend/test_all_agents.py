"""Comprehensive test suite for all AURA agents."""

from __future__ import annotations

import json
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.agents.coordinator import coordinate
from app.agents.supervisor import supervise
from app.agents.planner import planner_node
from app.agents.sales import sales_node
from app.agents.inventory import inventory_node
from app.agents.recommendation import recommendation_node
from app.agents.payment import payment_node
from app.agents.fulfillment import fulfillment_node
from app.agents.loyalty import loyalty_node
from app.agents.post_purchase import post_purchase_node
from app.agents.output_composer import output_composer_node


def run_all_agent_tests() -> None:
    print("=" * 70)
    print("RUNNING COMPREHENSIVE AURA AGENT SUITE")
    print("=" * 70)

    # 1. Recommendation Agent
    print("\n--- 1. Testing Recommendation Agent ---")
    state_rec = {
        "session_id": "test_rec",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Recommend running shoes under 2500"}],
        "intent": "recommendation",
        "max_price": 2500,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    rec_out = recommendation_node(state_rec)
    print("Output:", json.dumps(rec_out, indent=2))
    assert "recommendation" in rec_out["agent_outputs"]

    # 2. Payment Agent (create link & verify)
    print("\n--- 2. Testing Payment Agent ---")
    state_pay = {
        "session_id": "test_pay",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Generate checkout link for ORD-1001"}],
        "intent": "payment",
        "max_price": None,
        "plan": None,
        "agent_outputs": {"sales": [{"price": 1999}]},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    pay_out = payment_node(state_pay)
    print("Output:", json.dumps(pay_out, indent=2))
    assert "payment" in pay_out["agent_outputs"]

    # 3. Fulfillment Agent (order tracking & PIN check)
    print("\n--- 3. Testing Fulfillment Agent ---")
    state_ful = {
        "session_id": "test_ful",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Where is my order ORD-1001?"}],
        "intent": "fulfillment",
        "max_price": None,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    ful_out = fulfillment_node(state_ful)
    print("Output:", json.dumps(ful_out, indent=2))
    assert "fulfillment" in ful_out["agent_outputs"]

    # 4. Loyalty Agent
    print("\n--- 4. Testing Loyalty Agent ---")
    state_loy = {
        "session_id": "test_loy",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Check my loyalty points"}],
        "intent": "loyalty",
        "max_price": None,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    loy_out = loyalty_node(state_loy)
    print("Output:", json.dumps(loy_out, indent=2))
    assert "loyalty" in loy_out["agent_outputs"]

    # 5. Post-Purchase Agent
    print("\n--- 5. Testing Post-Purchase Agent ---")
    state_pp = {
        "session_id": "test_pp",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "What is the return policy for electronics?"}],
        "intent": "post_purchase",
        "max_price": None,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    pp_out = post_purchase_node(state_pp)
    print("Output:", json.dumps(pp_out, indent=2))
    assert "post_purchase" in pp_out["agent_outputs"]

    # 6. Output Composer Agent (Multi-Agent aggregation)
    print("\n--- 6. Testing Output Composer Agent ---")
    state_composer = {
        "session_id": "test_comp",
        "channel": "whatsapp_sim",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Find running shoes and check stock"}],
        "intent": "sales",
        "max_price": None,
        "plan": None,
        "agent_outputs": {
            "sales": [{"name": "Running Shoes", "price": 1999, "description": "Comfortable running shoes."}],
            "inventory": {"message": "Running Shoes is in stock (32 units available).", "in_stock": True},
            "fulfillment": {"message": "Estimated delivery to your location in 2 days."},
        },
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    composer_out = output_composer_node(state_composer)
    print("Composed Output:")
    print(composer_out["final_response"])
    assert composer_out.get("final_response") is not None

    # 7. Planner Node
    print("\n--- 7. Testing Planner Node ---")
    state_plan = {
        "session_id": "test_plan",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Find gaming keyboard, check availability and recommend one"}],
        "intent": "recommendation",
        "max_price": None,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    plan_out = planner_node(state_plan)
    print("Planner Output:", json.dumps(plan_out, indent=2))
    assert "plan" in plan_out

    print("\n" + "=" * 70)
    print("ALL AGENT TESTS PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_all_agent_tests()
