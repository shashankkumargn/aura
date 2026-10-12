
from app.agents.planner import create_plan


TEST_MESSAGE = (
    "Find me a gaming laptop under ₹80000, "
    "compare several options and recommend one."
)


result = create_plan(TEST_MESSAGE)

print("=" * 60)
print("Request:", TEST_MESSAGE)
print(result.model_dump_json(indent=2))
