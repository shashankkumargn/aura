from app.agents.sales import sales_node


state = {
    "session_id": "test",
    "channel": "web",
    "user_id": "user1",
    "messages": [],
    "intent": "shoes",
    "max_price": 2500,
    "plan": None,
    "agent_outputs": {},
    "retrieved_context": [],
    "policy_flags": [],
    "final_response": None,
}


result = sales_node(state)

print("=" * 60)
print("Sales Agent Test")
print("=" * 60)
print(result)