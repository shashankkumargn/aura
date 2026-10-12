"""Order placement, tracking, and returns tools backed by SQLite (aura.db)."""

from __future__ import annotations

import datetime
import uuid
from typing import Any
from langchain_core.tools import tool

from app.db.models import Order, OrderItem, Product
from app.db.session import SessionLocal


@tool
def place_order(user_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    """Place a new customer order; items is a list of dict(product_id=str, qty=int); returns dict(success=bool, order_id=str, total_amount=float, message=str)."""
    clean_uid = (user_id or "u123").strip()
    if not items:
        return {"success": False, "order_id": None, "total_amount": 0.0, "message": "Cannot place order: item list is empty."}

    db = SessionLocal()
    try:
        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        total = 0.0

        new_order = Order(
            id=order_id,
            customer_id=clean_uid,
            status="placed",
            channel="web",
            placed_at=datetime.datetime.utcnow(),
            payment_status="completed",
            shipment_status="placed",
        )
        db.add(new_order)

        for it in items:
            p_id = str(it.get("product_id", "")).strip().upper()
            qty = int(it.get("qty", 1))
            prod = db.query(Product).filter(Product.id == p_id).first()
            price = prod.price if prod else 999.0
            total += price * qty

            db.add(OrderItem(
                order_id=order_id,
                product_id=p_id,
                qty=qty,
                unit_price=price,
            ))
            # Decrement stock if product exists
            if prod and prod.stock_qty >= qty:
                prod.stock_qty -= qty

        db.commit()
        return {
            "success": True,
            "order_id": order_id,
            "total_amount": total,
            "status": "placed",
            "message": f"Order {order_id} placed successfully for ₹{total:,.2f}. Estimated dispatch in 24 hours.",
        }
    finally:
        db.close()


@tool
def get_shipment_status_mock(order_id: str) -> dict[str, Any]:
    """Track shipment status and delivery progress for an order; returns dict(found=bool, order_id=str, status=str, carrier=str, tracking_number=str, estimated_delivery=str, message=str)."""
    clean_id = (order_id or "").strip().upper()
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == clean_id).first()
        if not order:
            return {
                "found": False,
                "order_id": clean_id,
                "status": "Not Found",
                "message": f"Order ID '{clean_id}' was not found in our records.",
            }

        # Status progression based on age
        now = datetime.datetime.utcnow()
        hours_old = (now - order.placed_at).total_seconds() / 3600.0 if order.placed_at else 24

        if hours_old < 6:
            status = "placed"
            delivery_est = "3-4 business days"
        elif hours_old < 24:
            status = "packed"
            delivery_est = "2-3 business days"
        elif hours_old < 72:
            status = "shipped"
            delivery_est = "Tomorrow by 6:00 PM"
        else:
            status = "delivered"
            delivery_est = "Delivered"

        carrier = "BlueDart Express"
        tracking_no = f"BD-{clean_id[-4:]}99"

        return {
            "found": True,
            "order_id": order.id,
            "status": status,
            "carrier": carrier,
            "tracking_number": tracking_no,
            "estimated_delivery": delivery_est,
            "message": f"Order {order.id} is currently '{status.upper()}' via {carrier}. Estimated delivery: {delivery_est}.",
        }
    finally:
        db.close()


@tool
def submit_return_request(order_id: str, reason: str = "Customer requested return") -> dict[str, Any]:
    """Submit a return or refund request for an existing order; returns dict(success=bool, return_ticket=str, order_id=str, status=str, pickup_window=str, message=str)."""
    clean_id = (order_id or "").strip().upper()
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == clean_id).first()
        if not order:
            return {
                "success": False,
                "return_ticket": None,
                "order_id": clean_id,
                "message": f"Order '{clean_id}' not found.",
            }

        now = datetime.datetime.utcnow()
        days_old = (now - order.placed_at).days if order.placed_at else 1
        if days_old > 14:
            return {
                "success": False,
                "return_ticket": None,
                "order_id": clean_id,
                "message": f"Order {clean_id} was placed {days_old} days ago and is outside the 14-day return window.",
            }

        ticket_id = f"RET-{clean_id[-4:]}-01"
        return {
            "success": True,
            "return_ticket": ticket_id,
            "order_id": clean_id,
            "status": "Approved",
            "pickup_window": "Within 48 hours",
            "message": f"Return request {ticket_id} approved for Order {clean_id}. Free doorstep pickup scheduled within 48 hours.",
        }
    finally:
        db.close()


def track_shipment(order_id: str) -> dict[str, Any]:
    """Compatibility alias for get_shipment_status_mock."""
    return get_shipment_status_mock.invoke({"order_id": order_id})


def get_delivery_estimate(pincode: str) -> dict[str, Any]:
    """Calculate estimated delivery turnaround for a postal code."""
    clean_pin = pincode.strip()
    return {
        "pincode": clean_pin,
        "estimated_days": 2 if clean_pin.startswith(("11", "40", "56")) else 4,
        "message": f"Delivery to PIN code {clean_pin} estimated in 2-4 business days.",
    }


def initiate_return(order_id: str, reason: str = "Customer request") -> dict[str, Any]:
    """Compatibility alias for submit_return_request."""
    return submit_return_request.invoke({"order_id": order_id, "reason": reason})


def check_warranty_status(order_id_or_serial: str) -> dict[str, Any]:
    """Check warranty coverage for an order."""
    return {
        "found": True,
        "identifier": order_id_or_serial,
        "active": True,
        "coverage_type": "1-Year Comprehensive Manufacturer Warranty",
        "message": f"Warranty for {order_id_or_serial} is active (12 months authorized coverage).",
    }
