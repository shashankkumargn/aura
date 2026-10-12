"""SQLAlchemy models for AURA SQLite database."""

from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Product(Base):
    """Product catalog item."""

    __tablename__ = "products"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)
    subcategory = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    currency = Column(String, default="INR")
    description = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON-encoded string or comma-separated
    stock_qty = Column(Integer, default=10)
    image_url = Column(String, nullable=True)
    rating_avg = Column(Float, default=4.2)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    order_items = relationship("OrderItem", back_populates="product")


class Customer(Base):
    """Customer profile."""

    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    loyalty_points = Column(Integer, default=100)
    loyalty_tier = Column(String, default="Bronze")
    channel_preference = Column(String, default="web")

    orders = relationship("Order", back_populates="customer")
    loyalty_ledgers = relationship("LoyaltyLedger", back_populates="customer")


class Order(Base):
    """Customer order record."""

    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    status = Column(String, default="placed")  # placed, packed, shipped, delivered, cancelled
    channel = Column(String, default="web")
    placed_at = Column(DateTime, default=datetime.datetime.utcnow)
    payment_status = Column(String, default="completed")
    shipment_status = Column(String, default="placed")

    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Line item in an order."""

    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("orders.id"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    qty = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


class LoyaltyLedger(Base):
    """Loyalty points credit/debit audit entry."""

    __tablename__ = "loyalty_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    delta = Column(Integer, nullable=False)  # positive for earn, negative for redeem
    reason = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    customer = relationship("Customer", back_populates="loyalty_ledgers")


class PolicyDoc(Base):
    """Store policy document for customer assistance and RAG."""

    __tablename__ = "policy_docs"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    category = Column(String, nullable=False)


class AgentLog(Base):
    """Audit log for each conversation turn for analytics and explainability."""

    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True)
    user_id = Column(String, index=True)
    channel = Column(String)
    user_message = Column(Text)
    intent = Column(String)
    agents_used = Column(String)  # JSON-encoded list of agents
    latency_ms = Column(Float)
    final_response = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class Feedback(Base):
    """Human-in-the-loop thumbs up/down user feedback."""

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String)
    rating = Column(String)  # "up" or "down"
    comment = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
