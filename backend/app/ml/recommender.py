"""Hybrid recommendation engine combining Content-based TF-IDF and Collaborative filtering."""

from __future__ import annotations

import math
import re
from typing import Any
from langchain_core.tools import tool

from app.db.models import Customer, Order, OrderItem, Product
from app.db.session import SessionLocal


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())


@tool
def get_recommendations(user_id: str, k: int = 5) -> list[dict[str, Any]]:
    """Generate personalized product recommendations for a customer using hybrid collaborative and content filtering; returns list[dict(product_id, name, category, price, why, score)]."""
    clean_uid = (user_id or "u123").strip()
    db = SessionLocal()
    try:
        # 1. Fetch user's past purchase history
        user_orders = db.query(Order).filter(Order.customer_id == clean_uid).all()
        order_ids = [o.id for o in user_orders]
        past_items = db.query(OrderItem).filter(OrderItem.order_id.in_(order_ids)).all() if order_ids else []
        purchased_pids = set(item.product_id for item in past_items)

        all_products = db.query(Product).all()
        if not all_products:
            return []

        # If user has no history, fallback to top-rated items
        if not purchased_pids:
            top_rated = sorted(all_products, key=lambda p: (p.rating_avg or 0.0), reverse=True)[:k]
            return [
                {
                    "product_id": p.id,
                    "name": p.name,
                    "category": p.category,
                    "price": p.price,
                    "why": f"Trending top-rated item in {p.category} ({p.rating_avg}★)",
                    "score": round(p.rating_avg or 4.0, 2),
                }
                for p in top_rated
            ]

        # 2. Collaborative filtering: item-item co-occurrence in orders
        all_order_items = db.query(OrderItem).all()
        order_to_items: dict[str, list[str]] = {}
        for oi in all_order_items:
            order_to_items.setdefault(oi.order_id, []).append(oi.product_id)

        co_occurrence: dict[str, int] = {}
        co_source: dict[str, str] = {}
        for o_id, pids in order_to_items.items():
            intersection = set(pids).intersection(purchased_pids)
            if intersection:
                source_pid = list(intersection)[0]
                for other_pid in pids:
                    if other_pid not in purchased_pids:
                        co_occurrence[other_pid] = co_occurrence.get(other_pid, 0) + 1
                        co_source[other_pid] = source_pid

        # 3. Content-based: TF-IDF similarity to user purchased product descriptions
        purchased_objs = [p for p in all_products if p.id in purchased_pids]
        user_corpus = " ".join(f"{p.name} {p.category} {p.subcategory or ''} {p.description or ''}" for p in purchased_objs)
        user_tokens = set(_tokenize(user_corpus))

        candidates = [p for p in all_products if p.id not in purchased_pids]
        scored_candidates: list[dict[str, Any]] = []

        for p in candidates:
            p_text = f"{p.name} {p.category} {p.subcategory or ''} {p.description or ''}"
            p_tokens = _tokenize(p_text)
            token_overlap = len(user_tokens.intersection(set(p_tokens)))

            content_score = token_overlap / (math.sqrt(len(p_tokens) or 1) + 1.0)
            collab_score = co_occurrence.get(p.id, 0) * 1.5

            total_score = content_score + collab_score

            if collab_score > 0 and p.id in co_source:
                src_obj = next((x for x in all_products if x.id == co_source[p.id]), None)
                src_name = src_obj.name if src_obj else "past order"
                why = f"Frequently bought together with {src_name}"
            elif token_overlap > 0:
                why = f"Matches your interest in {p.category} and related features"
            else:
                why = f"Highly rated in {p.category} ({p.rating_avg}★)"

            scored_candidates.append({
                "product_id": p.id,
                "name": p.name,
                "category": p.category,
                "price": p.price,
                "why": why,
                "score": round(total_score, 2),
            })

        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates[:k]
    finally:
        db.close()
