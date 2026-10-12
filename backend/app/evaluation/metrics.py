"""Evaluation metrics for AURA agent pipeline quality.

Computes latency statistics, intent-routing accuracy, and tool-call success
rates from the agent_logs table in aura.db.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

from app.db.models import AgentLog
from app.db.session import SessionLocal


def compute_latency_stats(limit: int = 200) -> dict[str, Any]:
    """Compute mean, median, p95, and max latency from recent agent logs.

    Returns dict(count, mean_ms, median_ms, p95_ms, max_ms).
    """
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .filter(AgentLog.latency_ms.isnot(None))
            .order_by(AgentLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        if not logs:
            return {"count": 0, "mean_ms": 0, "median_ms": 0, "p95_ms": 0, "max_ms": 0}

        latencies = sorted(l.latency_ms for l in logs)
        p95_idx = int(len(latencies) * 0.95)

        return {
            "count": len(latencies),
            "mean_ms": round(statistics.mean(latencies), 2),
            "median_ms": round(statistics.median(latencies), 2),
            "p95_ms": round(latencies[min(p95_idx, len(latencies) - 1)], 2),
            "max_ms": round(max(latencies), 2),
        }
    finally:
        db.close()


def compute_intent_distribution(limit: int = 200) -> dict[str, int]:
    """Count how often each intent was classified across recent logs.

    Returns dict mapping intent label to count.
    """
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .order_by(AgentLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        dist: dict[str, int] = {}
        for l in logs:
            intent = l.intent or "unclassified"
            dist[intent] = dist.get(intent, 0) + 1
        return dist
    finally:
        db.close()


def compute_agent_utilization(limit: int = 200) -> dict[str, int]:
    """Count how often each specialized agent was invoked.

    Returns dict mapping agent name to invocation count.
    """
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .order_by(AgentLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        util: dict[str, int] = {}
        for l in logs:
            agents = json.loads(l.agents_used) if l.agents_used else []
            for a in agents:
                util[a] = util.get(a, 0) + 1
        return util
    finally:
        db.close()


def compute_channel_distribution(limit: int = 200) -> dict[str, int]:
    """Count messages by channel (web, mobile, whatsapp_sim, kiosk_sim).

    Returns dict mapping channel to count.
    """
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .order_by(AgentLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        dist: dict[str, int] = {}
        for l in logs:
            ch = l.channel or "web"
            dist[ch] = dist.get(ch, 0) + 1
        return dist
    finally:
        db.close()


KNOWN_AGENT_IDS = {
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

AGENT_ALIASES = {
    "product_search": "sales",
    "order_status": "fulfillment",
    "tracking": "fulfillment",
    "return_or_complaint": "post_purchase",
    "returns": "post_purchase",
    "recommend": "recommendation",
    "stock": "inventory",
    "checkout": "payment",
    "points": "loyalty",
}


def _parse_agents(raw: str | None) -> list[str]:
    """Parse agents_used JSON from an AgentLog row into a clean agent-id list."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    agents: list[str] = []
    for item in parsed:
        name = str(item or "").strip().lower()
        name = AGENT_ALIASES.get(name, name)
        if name in KNOWN_AGENT_IDS and name not in agents:
            agents.append(name)
    return agents


def compute_agent_stats(limit: int = 500) -> dict[str, Any]:
    """Aggregate real per-agent call counts and average turn latency from agent_logs.

    Returns dict(agents=[{id, calls, avg_ms}], total_turns, recent_activity=[int]).
    avg_ms is the mean of turn latency_ms for turns that included that agent.
    """
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .order_by(AgentLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        calls: dict[str, int] = {}
        latency_sums: dict[str, float] = {}
        latency_counts: dict[str, int] = {}

        for log in logs:
            agents = _parse_agents(log.agents_used)
            # Older FAQ / incomplete rows: count the always-on pipeline only.
            if not agents:
                agents = ["coordinator", "supervisor", "output_composer"]
            for agent_id in agents:
                calls[agent_id] = calls.get(agent_id, 0) + 1
                if log.latency_ms is not None:
                    latency_sums[agent_id] = latency_sums.get(agent_id, 0.0) + float(log.latency_ms)
                    latency_counts[agent_id] = latency_counts.get(agent_id, 0) + 1

        agent_rows = []
        for agent_id, count in sorted(calls.items(), key=lambda item: (-item[1], item[0])):
            n = latency_counts.get(agent_id, 0)
            avg_ms = round(latency_sums[agent_id] / n, 1) if n else 0.0
            agent_rows.append({"id": agent_id, "calls": count, "avg_ms": avg_ms})

        # Newest-first logs → reverse so sparkline reads left(older) → right(newer).
        recent = list(reversed(logs[:12]))
        activity = [max(1, int(round((log.latency_ms or 0) / 250.0))) for log in recent]

        return {
            "agents": agent_rows,
            "total_turns": len(logs),
            "recent_activity": activity,
        }
    finally:
        db.close()


def compute_session_summaries(limit: int = 200) -> list[dict[str, Any]]:
    """Build session summaries from agent_logs (newest session activity first)."""
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .order_by(AgentLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        sessions: dict[str, dict[str, Any]] = {}
        for log in logs:
            sid = log.session_id or "unknown"
            if sid not in sessions:
                sessions[sid] = {
                    "session_id": sid,
                    "user_id": log.user_id,
                    "channel": log.channel,
                    "turn_count": 0,
                    "last_intent": log.intent,
                    "last_user_message": log.user_message,
                    "last_response": log.final_response,
                    "last_agents": _parse_agents(log.agents_used),
                    "last_latency_ms": log.latency_ms,
                    "last_timestamp": log.timestamp.isoformat() if log.timestamp else None,
                }
            sessions[sid]["turn_count"] += 1

        return sorted(
            sessions.values(),
            key=lambda row: row.get("last_timestamp") or "",
            reverse=True,
        )
    finally:
        db.close()
