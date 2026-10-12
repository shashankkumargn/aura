"""Smoke test: Coordinator → Supervisor routing."""

from __future__ import annotations

from app.agents.coordinator import coordinate
from app.agents.supervisor import supervise

TEST_MESSAGES = [
    "Is iPhone 15 available?",
    "Show me Nike shoes under ₹2500",
    "Find me a gaming laptop under ₹80000, compare several options and recommend one.",
    "Hello",
]


def main() -> None:
    for message in TEST_MESSAGES:
        print("=" * 60)
        print(f"Request: {message}")
        coordinator_result = coordinate(message)
        supervisor_result = supervise(coordinator_result)
        print("Coordinator:")
        print(coordinator_result.model_dump_json(indent=2))
        print("Supervisor:")
        print(supervisor_result.model_dump_json(indent=2))
        print()


if __name__ == "__main__":
    main()
