"""Test script for AURA Inventory Agent and Tools."""

from __future__ import annotations

from app.agents.inventory import inventory_node
from app.tools.inventory_tools import check_stock, get_product_availability


def test_tools() -> None:
    print("=" * 60)
    print("TESTING INVENTORY TOOLS")
    print("=" * 60)

    res1 = check_stock("Headphones")
    print("1. check_stock('Headphones'):")
    print(res1)

    res2 = get_product_availability("P003")
    print("\n2. get_product_availability('P003') [Running Shoes]:")
    print(res2)

    res3 = check_stock("iPhone 15")
    print("\n3. check_stock('iPhone 15'):")
    print(res3)


def test_agent_node() -> None:
    print("\n" + "=" * 60)
    print("TESTING INVENTORY AGENT NODE")
    print("=" * 60)

    # Test A: Direct user inquiry for headphones
    state_a = {
        "session_id": "test_inv_1",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Is Wireless Bluetooth Headphones in stock?"}],
        "intent": "inventory",
        "max_price": None,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    out_a = inventory_node(state_a)
    print("\nA. User asks: 'Is Wireless Bluetooth Headphones in stock?'")
    print(out_a)

    # Test B: Direct user inquiry for unavailable item
    state_b = {
        "session_id": "test_inv_2",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Is iPhone 15 available?"}],
        "intent": "inventory",
        "max_price": None,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    out_b = inventory_node(state_b)
    print("\nB. User asks: 'Is iPhone 15 available?'")
    print(out_b)

    # Test C: Chained after Sales agent output
    state_c = {
        "session_id": "test_inv_3",
        "channel": "web",
        "user_id": "u123",
        "messages": [{"role": "user", "content": "Find mechanical keyboard and check stock"}],
        "intent": "inventory",
        "max_price": None,
        "plan": None,
        "agent_outputs": {
            "sales": [
                {"id": "P004", "name": "Mechanical Gaming Keyboard", "price": 2999}
            ]
        },
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }
    out_c = inventory_node(state_c)
    print("\nC. Multi-step chained after sales output:")
    print(out_c)


if __name__ == "__main__":
    test_tools()
    test_agent_node()
