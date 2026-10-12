"""Smoke test for the AURA Coordinator (intent classification)."""

from __future__ import annotations

from app.agents.coordinator import coordinate

TEST_MESSAGES = [
    "Show me Nike shoes under ₹2500",
    "Recommend a smartphone under ₹20000 for gaming",
    "Find me a gaming laptop under ₹80000, compare several options and recommend one.",
    "Is iPhone 15 available?",
    "Where is my order?",
    "Hello",
]


def main() -> None:
    for message in TEST_MESSAGES:
        print("=" * 60)
        print(f"Request: {message}")
        result = coordinate(message)
        print(result.model_dump_json(indent=2))
        print()


if __name__ == "__main__":
    main()
