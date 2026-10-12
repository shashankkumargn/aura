"""Product catalog tools for AURA backed by SQLite (aura.db)."""

from __future__ import annotations

import json
from typing import Any
from langchain_core.tools import tool
from sqlalchemy import and_, or_

from app.db.models import Product
from app.db.session import SessionLocal


@tool
def search_products(
    query: str,
    category: str | None = None,
    max_price: int | None = None,
) -> list[dict[str, Any]]:
    """Search products by keywords, category, and maximum price; returns list[dict(id, name, category, price, stock_qty, description)]."""
    clean_query = (query or "").strip().lower()

    db = SessionLocal()
    try:
        q = db.query(Product)

        if clean_query:
            words = clean_query.split()
            # Match if all words appear in name, category, subcategory, brand, or description
            word_conditions = [
                or_(
                    Product.name.ilike(f"%{w}%"),
                    Product.category.ilike(f"%{w}%"),
                    Product.subcategory.ilike(f"%{w}%"),
                    Product.description.ilike(f"%{w}%"),
                    Product.brand.ilike(f"%{w}%"),
                )
                for w in words
            ]
            q = q.filter(and_(*word_conditions))

        if category:
            q = q.filter(Product.category.ilike(f"%{category}%"))
        if max_price is not None:
            q = q.filter(Product.price <= float(max_price))

        products = q.order_by(Product.price.asc()).limit(10).all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "subcategory": p.subcategory,
                "brand": p.brand,
                "price": p.price,
                "currency": p.currency,
                "stock_qty": p.stock_qty,
                "rating_avg": p.rating_avg,
                "description": p.description,
            }
            for p in products
        ]
    finally:
        db.close()


@tool
def get_product(product_id: str) -> dict[str, Any]:
    """Look up product details by unique product ID; returns dict(id, name, price, stock_qty, description) or error dict."""
    db = SessionLocal()
    try:
        p = db.query(Product).filter(Product.id == product_id.strip().upper()).first()
        if not p:
            return {"found": False, "product_id": product_id, "message": f"Product '{product_id}' not found."}
        return {
            "found": True,
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "subcategory": p.subcategory,
            "brand": p.brand,
            "price": p.price,
            "stock_qty": p.stock_qty,
            "rating_avg": p.rating_avg,
            "description": p.description,
        }
    finally:
        db.close()