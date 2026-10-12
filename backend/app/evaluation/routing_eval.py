"""Routing accuracy evaluation for the AURA Coordinator agent.

Runs a set of labeled test queries through the Coordinator and computes
accuracy, per-intent precision, and a confusion matrix.
"""

from __future__ import annotations

from typing import Any

from app.agents.coordinator import coordinate


# Ground-truth test cases: (user_message, expected_intent)
ROUTING_TEST_CASES: list[tuple[str, str]] = [
    # product_search
    ("Show me wireless earphones under 2000", "product_search"),
    ("Do you have Nike running shoes?", "product_search"),
    ("Search for smartwatches", "product_search"),
    # recommendation
    ("Recommend headphones for me", "recommendation"),
    ("What should I buy for a birthday gift?", "recommendation"),
    ("Compare boAt and Sony earbuds", "recommendation"),
    # inventory
    ("Is the JBL speaker in stock?", "inventory"),
    ("Check availability of P001", "inventory"),
    # order_status
    ("Where is my order ORD-1001?", "order_status"),
    ("Track my delivery", "order_status"),
    # payment
    ("Pay for my order ORD-1001 using UPI", "payment"),
    ("Process checkout for my cart", "payment"),
    # loyalty
    ("How many reward points do I have?", "loyalty"),
    ("Redeem 200 loyalty points", "loyalty"),
    # return_or_complaint
    ("I want to return my order ORD-1002", "return_or_complaint"),
    ("What is your refund policy?", "return_or_complaint"),
    ("My product arrived damaged", "return_or_complaint"),
    # general_faq
    ("Hello!", "general_faq"),
    ("What can you help me with?", "general_faq"),
    ("Thanks for your help", "general_faq"),
]


def run_routing_eval() -> dict[str, Any]:
    """Run all routing test cases and compute accuracy metrics.

    Returns dict(total, correct, accuracy, per_intent, failures).
    """
    results: list[dict[str, Any]] = []
    correct = 0
    per_intent_correct: dict[str, int] = {}
    per_intent_total: dict[str, int] = {}
    failures: list[dict[str, str]] = []

    for user_msg, expected in ROUTING_TEST_CASES:
        try:
            res = coordinate(user_msg)
            predicted = res.intent
        except Exception as exc:
            predicted = f"ERROR: {exc}"

        is_correct = predicted == expected
        if is_correct:
            correct += 1

        per_intent_total[expected] = per_intent_total.get(expected, 0) + 1
        if is_correct:
            per_intent_correct[expected] = per_intent_correct.get(expected, 0) + 1
        else:
            failures.append({
                "message": user_msg,
                "expected": expected,
                "predicted": predicted,
            })

        results.append({
            "message": user_msg,
            "expected": expected,
            "predicted": predicted,
            "correct": is_correct,
        })

    total = len(ROUTING_TEST_CASES)
    accuracy = round(correct / total, 4) if total else 0.0

    per_intent: dict[str, dict[str, Any]] = {}
    for intent in per_intent_total:
        t = per_intent_total[intent]
        c = per_intent_correct.get(intent, 0)
        per_intent[intent] = {
            "total": t,
            "correct": c,
            "accuracy": round(c / t, 4) if t else 0.0,
        }

    return {
        "total": total,
        "correct": correct,
        "accuracy": accuracy,
        "per_intent": per_intent,
        "failures": failures,
        "details": results,
    }


if __name__ == "__main__":
    print("Running AURA Routing Evaluation...\n")
    report = run_routing_eval()
    print(f"Overall Accuracy: {report['accuracy'] * 100:.1f}% ({report['correct']}/{report['total']})\n")

    print("Per-Intent Breakdown:")
    for intent, stats in report["per_intent"].items():
        print(f"  {intent:25s} → {stats['accuracy']*100:5.1f}% ({stats['correct']}/{stats['total']})")

    if report["failures"]:
        print(f"\nMisclassifications ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"  ✗ '{f['message']}' → expected={f['expected']}, got={f['predicted']}")
