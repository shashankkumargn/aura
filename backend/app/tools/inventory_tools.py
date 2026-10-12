"""Inventory and stock inspection tools backed by SQLite (aura.db)."""

from __future__ import annotations

from typing import Any
from langchain_core.tools import tool

from app.db.models import Product
from app.db.session import SessionLocal


@tool
def check_stock(product_id: str) -> dict[str, Any]:
    """Check stock quantity and availability for a product by ID or name; returns dict(found=bool, product_id=str, name=str, stock_qty=int, in_stock=bool, low_stock=bool, message=str)."""
    clean = (product_id or "").strip()
    if not clean:
        return {"found": False, "stock_qty": 0, "in_stock": False, "message": "No product specified."}

    db = SessionLocal()
    try:
        # Search by exact ID first, then case-insensitive name match
        p = db.query(Product).filter(Product.id == clean.upper()).first()
        if not p:
            p = db.query(Product).filter(Product.name.ilike(f"%{clean}%")).first()

        if not p:
            return {
                "found": False,
                "product_id": clean,
                "stock_qty": 0,
                "in_stock": False,
                "low_stock": False,
                "message": f"Product '{clean}' not found in inventory catalog.",
            }

        stock = p.stock_qty
        in_stock = stock > 0
        low_stock = 0 < stock <= 5
        status_text = "in stock" if in_stock else "out of stock"
        low_text = " (Low stock alert: few units left!)" if low_stock else ""

        return {
            "found": True,
            "product_id": p.id,
            "name": p.name,
            "stock_qty": stock,
            "in_stock": in_stock,
            "low_stock": low_stock,
            "message": f"'{p.name}' is {status_text} with {stock} units available.{low_text}",
        }
    finally:
        db.close()


def get_low_stock_products(threshold: int = 5) -> list[dict[str, Any]]:
    """Retrieve all products below stock threshold (plain helper for dashboard)."""
    db = SessionLocal()
    try:
        prods = db.query(Product).filter(Product.stock_qty <= threshold).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "stock_qty": p.stock_qty,
                "price": p.price,
            }
            for p in prods
        ]
    finally:
        db.close()


def get_product_availability(product_id: str) -> dict[str, Any]:
    """Compatibility alias for check_stock."""
    return check_stock.invoke({"product_id": product_id})
