"""AURA FastAPI application entrypoint with chat and admin endpoints."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.models import AgentLog, Feedback, Order, PolicyDoc, Product
from app.db.session import get_db, init_db
from app.evaluation.metrics import (
    compute_agent_stats,
    compute_channel_distribution,
    compute_intent_distribution,
    compute_latency_stats,
    compute_session_summaries,
)
from app.graph import graph
from app.memory.short_term import append_turn, get_history
from app.state import AuraState

PIPELINE_AGENT_IDS = {
    "coordinator",
    "supervisor",
    "planner",
    "sales",
    "recommendation",
    "inventory",
    "payment",
    "fulfillment",
    "loyalty",
    "post_purchase",
    "output_composer",
}


def _resolve_agents_used(final_state: dict[str, Any]) -> list[str]:
    """Build the ordered list of agents that actually ran for this turn."""
    agents: list[str] = ["coordinator", "supervisor"]
    plan = final_state.get("plan") or []
    agent_outputs = final_state.get("agent_outputs") or {}

    domain_agents = [
        str(name).strip().lower()
        for name in agent_outputs.keys()
        if str(name).strip().lower() in PIPELINE_AGENT_IDS
        and str(name).strip().lower()
        not in {"coordinator", "supervisor", "planner", "output_composer"}
    ]

    if plan and len(plan) > 1:
        agents.append("planner")
        for step in plan:
            target = str(step.get("agent", "")).strip().lower()
            if target in {"product_search", "sales"}:
                target = "sales"
            elif target in {"order_status", "fulfillment", "tracking"}:
                target = "fulfillment"
            elif target in {"return_or_complaint", "returns", "warranty"}:
                target = "post_purchase"
            if target in PIPELINE_AGENT_IDS and target not in agents and target != "planner":
                agents.append(target)

    for name in domain_agents:
        if name not in agents:
            agents.append(name)

    agents.append("output_composer")
    return agents

init_db()

app = FastAPI(
    title="AURA API",
    description="Agentic Unified Retail Assistant for Omni-Channel Commerce",
    version="1.0.0",
)

# Enable CORS for frontend and dashboard access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    session_id: str = Field(default="demo-session")
    channel: str = Field(default="web")  # "web", "mobile", "whatsapp_sim", "kiosk_sim"
    user_id: str = Field(default="u123")
    message: str


class ChatResponse(BaseModel):
    response: str
    intent: str | None = None
    agents_used: list[str] = Field(default_factory=list)
    retrieved_sources: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    session_id: str
    rating: str  # "up" or "down"
    comment: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check for the AURA backend."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Run full hierarchical multi-agent graph with memory and audit logging."""
    start_time = time.time()

    # 1. Fetch short term memory context
    history = get_history(payload.session_id, max_turns=6)
    messages = list(history)
    messages.append({"role": "user", "content": payload.message})

    state_input: AuraState = {
        "session_id": payload.session_id,
        "channel": payload.channel,
        "user_id": payload.user_id,
        "messages": messages,
        "intent": None,
        "plan": None,
        "agent_outputs": {},
        "retrieved_context": [],
        "policy_flags": [],
        "final_response": None,
    }

    try:
        final_state = graph.invoke(state_input)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {exc}") from exc

    latency_ms = (time.time() - start_time) * 1000.0
    final_reply = final_state.get("final_response") or "I could not generate a response. Please try again."
    intent = final_state.get("intent")
    agents_used = _resolve_agents_used(final_state)

    retrieved_sources = final_state.get("retrieved_context") or []

    # 2. Update short-term session memory
    append_turn(payload.session_id, "user", payload.message)
    append_turn(payload.session_id, "assistant", final_reply)

    # 3. Persist turn audit log in database
    log_entry = AgentLog(
        session_id=payload.session_id,
        user_id=payload.user_id,
        channel=payload.channel,
        user_message=payload.message,
        intent=intent or "unclassified",
        agents_used=json.dumps(agents_used),
        latency_ms=round(latency_ms, 2),
        final_response=final_reply,
    )
    db.add(log_entry)
    db.commit()

    return ChatResponse(
        response=final_reply,
        intent=intent,
        agents_used=agents_used,
        retrieved_sources=retrieved_sources,
    )


@app.get("/admin/orders")
def get_admin_orders(limit: int = 50, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Retrieve recent orders for the analytics dashboard."""
    orders = db.query(Order).order_by(Order.placed_at.desc()).limit(limit).all()
    return [
        {
            "id": o.id,
            "customer_id": o.customer_id,
            "status": o.status,
            "channel": o.channel,
            "placed_at": o.placed_at.isoformat() if o.placed_at else None,
            "payment_status": o.payment_status,
            "shipment_status": o.shipment_status,
        }
        for o in orders
    ]


@app.get("/admin/products")
def get_admin_products(limit: int = 100, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Retrieve catalog products for dashboard metrics."""
    products = db.query(Product).order_by(Product.id.asc()).limit(limit).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "brand": p.brand,
            "price": p.price,
            "stock_qty": p.stock_qty,
            "rating_avg": p.rating_avg,
        }
        for p in products
    ]


@app.get("/admin/agent-logs")
def get_admin_logs(limit: int = 50, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Retrieve recent agent turn logs for explainability and latency monitoring."""
    logs = db.query(AgentLog).order_by(AgentLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "session_id": l.session_id,
            "user_id": l.user_id,
            "channel": l.channel,
            "user_message": l.user_message,
            "intent": l.intent,
            "agents_used": json.loads(l.agents_used) if l.agents_used else [],
            "latency_ms": l.latency_ms,
            "final_response": l.final_response,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in logs
    ]


@app.get("/admin/agent-stats")
def get_agent_stats(limit: int = 500) -> dict[str, Any]:
    """Live per-agent call counts and average latencies from agent_logs."""
    return compute_agent_stats(limit=limit)


@app.get("/admin/sessions")
def get_admin_sessions(limit: int = 200) -> list[dict[str, Any]]:
    """Live conversation sessions aggregated from agent_logs."""
    return compute_session_summaries(limit=limit)


@app.get("/admin/overview")
def get_admin_overview(limit: int = 200) -> dict[str, Any]:
    """Live workspace overview metrics from agent_logs."""
    return {
        "latency": compute_latency_stats(limit=limit),
        "intents": compute_intent_distribution(limit=limit),
        "channels": compute_channel_distribution(limit=limit),
        "agent_stats": compute_agent_stats(limit=limit),
        "sessions": compute_session_summaries(limit=limit)[:10],
    }


@app.get("/admin/knowledge")
def get_admin_knowledge(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Live catalog and policy documents used by tools/RAG."""
    products = db.query(Product).order_by(Product.id.asc()).limit(100).all()
    policies = db.query(PolicyDoc).order_by(PolicyDoc.id.asc()).all()
    return {
        "product_count": db.query(Product).count(),
        "policy_count": db.query(PolicyDoc).count(),
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "brand": p.brand,
                "price": p.price,
                "stock_qty": p.stock_qty,
            }
            for p in products
        ],
        "policies": [
            {
                "id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "text": doc.text,
            }
            for doc in policies
        ],
    }


@app.post("/admin/feedback")
@app.post("/feedback")
def submit_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    """Human-in-the-loop feedback logger."""
    entry = Feedback(
        session_id=payload.session_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(entry)
    db.commit()
    return {"status": "ok"}
