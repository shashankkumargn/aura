"""Simulated payment processing tools for AURA."""

from __future__ import annotations

import hashlib
import random
from typing import Any
from langchain_core.tools import tool


@tool
def process_payment_mock(order_id: str, method: str = "UPI") -> dict[str, Any]:
    """Process a simulated payment transaction for an order; returns dict(status=str, txn_id=str, order_id=str, method=str, message=str)."""
    clean_id = (order_id or "ORD-1001").strip().upper()
    # Seed based on order_id to make simulation deterministic
    seed_val = int(hashlib.md5(clean_id.encode()).hexdigest(), 16)
    rng = random.Random(seed_val)

    # 90% success, 10% failure simulation
    is_success = rng.random() < 0.90
    txn_id = f"TXN-{clean_id[-4:]}-{rng.randint(1000, 9999)}"

    if is_success:
        return {
            "status": "SUCCESS",
            "txn_id": txn_id,
            "order_id": clean_id,
            "method": method.upper(),
            "message": f"Simulated payment of order {clean_id} succeeded via {method.upper()}. Transaction ID: {txn_id}.",
        }
    return {
        "status": "FAILED",
        "txn_id": txn_id,
        "order_id": clean_id,
        "method": method.upper(),
        "message": f"Simulated payment for order {clean_id} failed (simulated bank authorization decline).",
    }


def create_payment_link(order_id: str, amount: float, currency: str = "INR") -> dict[str, Any]:
    """Compatibility alias for generating checkout link."""
    res = process_payment_mock.invoke({"order_id": order_id, "method": "UPI"})
    return {
        "success": res["status"] == "SUCCESS",
        "payment_id": res["txn_id"],
        "payment_url": f"https://pay.aura-retail.sim/checkout/{res['txn_id']}",
        "amount": amount,
        "currency": currency,
        "status": "COMPLETED" if res["status"] == "SUCCESS" else "FAILED",
        "message": res["message"],
    }


def verify_payment_status(payment_id: str) -> dict[str, Any]:
    """Compatibility alias for checking transaction status."""
    return {
        "found": True,
        "payment_id": payment_id,
        "status": "COMPLETED",
        "amount": 1999.0,
        "currency": "INR",
        "message": f"Payment {payment_id} is verified and COMPLETED.",
    }
