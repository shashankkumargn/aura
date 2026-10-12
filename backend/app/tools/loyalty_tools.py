"""Customer loyalty and rewards tools backed by SQLite (aura.db)."""

from __future__ import annotations

import datetime
from typing import Any
from langchain_core.tools import tool

from app.db.models import Customer, LoyaltyLedger
from app.db.session import SessionLocal


@tool
def get_loyalty_balance(user_id: str) -> dict[str, Any]:
    """Retrieve customer loyalty tier, active points balance, and monetary discount value; returns dict(found=bool, user_id=str, tier=str, points=int, monetary_value=float, message=str)."""
    clean_uid = (user_id or "u123").strip()
    db = SessionLocal()
    try:
        cust = db.query(Customer).filter(Customer.id == clean_uid).first()
        if not cust:
            return {
                "found": False,
                "user_id": clean_uid,
                "tier": "Bronze",
                "points": 0,
                "monetary_value": 0.0,
                "message": f"Customer '{clean_uid}' does not have an active loyalty account.",
            }

        pts = cust.loyalty_points
        val = pts * 0.5  # ₹0.50 per point
        return {
            "found": True,
            "user_id": cust.id,
            "name": cust.name,
            "tier": cust.loyalty_tier,
            "points": pts,
            "monetary_value": val,
            "currency": "INR",
            "message": f"Customer {cust.name} has {pts} {cust.loyalty_tier} points (monetary value ₹{val:,.2f}).",
        }
    finally:
        db.close()


@tool
def redeem_points(user_id: str, points: int) -> dict[str, Any]:
    """Redeem customer reward points toward an order discount; returns dict(success=bool, user_id=str, points_redeemed=int, discount_amount=float, remaining_points=int, message=str)."""
    clean_uid = (user_id or "u123").strip()
    db = SessionLocal()
    try:
        cust = db.query(Customer).filter(Customer.id == clean_uid).first()
        if not cust:
            return {"success": False, "user_id": clean_uid, "points_redeemed": 0, "discount_amount": 0.0, "message": f"Customer '{clean_uid}' not found."}

        available = cust.loyalty_points
        if points > available:
            return {
                "success": False,
                "user_id": clean_uid,
                "points_redeemed": 0,
                "discount_amount": 0.0,
                "remaining_points": available,
                "message": f"Cannot redeem {points} points: your current balance is {available} points.",
            }

        discount = points * 0.5
        cust.loyalty_points -= points

        # Record in audit ledger
        db.add(LoyaltyLedger(
            customer_id=clean_uid,
            delta=-points,
            reason=f"Redeemed {points} points for ₹{discount:,.2f} discount voucher",
            timestamp=datetime.datetime.utcnow(),
        ))
        db.commit()

        return {
            "success": True,
            "user_id": clean_uid,
            "points_redeemed": points,
            "discount_amount": discount,
            "remaining_points": cust.loyalty_points,
            "message": f"Successfully redeemed {points} points for a ₹{discount:,.2f} discount. Remaining balance: {cust.loyalty_points} points.",
        }
    finally:
        db.close()


def redeem_loyalty_points(user_id: str, points: int) -> dict[str, Any]:
    """Compatibility alias for redeem_points."""
    return redeem_points.invoke({"user_id": user_id, "points": points})
