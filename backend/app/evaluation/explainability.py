"""Explainability module for AURA agent decision tracing.

Provides functions to generate human-readable decision traces, agent-chain
summaries, and formatted explainability reports from agent logs.
"""

from __future__ import annotations

import json
from typing import Any

from app.db.models import AgentLog, Feedback
from app.db.session import SessionLocal


def get_decision_trace(session_id: str) -> list[dict[str, Any]]:
    """Retrieve the full agent decision chain for a session.

    Returns a chronological list of dicts with user_message, intent,
    agents_used, latency_ms, and final_response for each turn.
    """
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .filter(AgentLog.session_id == session_id)
            .order_by(AgentLog.timestamp.asc())
            .all()
        )
        return [
            {
                "turn": idx + 1,
                "user_message": l.user_message,
                "intent": l.intent,
                "agents_used": json.loads(l.agents_used) if l.agents_used else [],
                "latency_ms": l.latency_ms,
                "final_response": l.final_response,
                "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            }
            for idx, l in enumerate(logs)
        ]
    finally:
        db.close()


def build_explainability_report(session_id: str) -> dict[str, Any]:
    """Build a structured explainability report for a conversation session.

    Returns dict with session metadata, decision trace, agent usage summary,
    latency stats, and any user feedback.
    """
    db = SessionLocal()
    try:
        logs = (
            db.query(AgentLog)
            .filter(AgentLog.session_id == session_id)
            .order_by(AgentLog.timestamp.asc())
            .all()
        )
        if not logs:
            return {"session_id": session_id, "error": "No logs found for this session."}

        # Build the decision trace
        trace: list[dict[str, Any]] = []
        all_agents: list[str] = []
        latencies: list[float] = []
        intents: list[str] = []

        for idx, l in enumerate(logs):
            agents = json.loads(l.agents_used) if l.agents_used else []
            all_agents.extend(agents)
            if l.latency_ms is not None:
                latencies.append(l.latency_ms)
            intents.append(l.intent or "unclassified")

            trace.append({
                "turn": idx + 1,
                "user_message": l.user_message,
                "classified_intent": l.intent,
                "agents_invoked": agents,
                "latency_ms": l.latency_ms,
                "response_preview": (l.final_response or "")[:200],
            })

        # Agent usage summary
        agent_counts: dict[str, int] = {}
        for a in all_agents:
            agent_counts[a] = agent_counts.get(a, 0) + 1

        # Latency summary
        latency_summary = {}
        if latencies:
            latency_summary = {
                "mean_ms": round(sum(latencies) / len(latencies), 2),
                "min_ms": round(min(latencies), 2),
                "max_ms": round(max(latencies), 2),
            }

        # Fetch user feedback
        fb_entries = (
            db.query(Feedback)
            .filter(Feedback.session_id == session_id)
            .all()
        )
        feedback = [
            {
                "rating": f.rating,
                "comment": f.comment,
                "timestamp": f.timestamp.isoformat() if f.timestamp else None,
            }
            for f in fb_entries
        ]

        return {
            "session_id": session_id,
            "total_turns": len(trace),
            "user_id": logs[0].user_id,
            "channel": logs[0].channel,
            "intents_seen": list(set(intents)),
            "agent_usage_summary": agent_counts,
            "latency_summary": latency_summary,
            "decision_trace": trace,
            "user_feedback": feedback,
        }
    finally:
        db.close()


def format_trace_markdown(session_id: str) -> str:
    """Generate a markdown-formatted explainability trace for display.

    Returns a multi-line markdown string suitable for Streamlit or docs.
    """
    report = build_explainability_report(session_id)
    if "error" in report:
        return f"**Error:** {report['error']}"

    lines: list[str] = []
    lines.append(f"# Explainability Report — Session `{session_id}`")
    lines.append(f"- **User:** {report.get('user_id', 'unknown')}")
    lines.append(f"- **Channel:** {report.get('channel', 'web')}")
    lines.append(f"- **Total turns:** {report['total_turns']}")
    lines.append("")

    if report.get("latency_summary"):
        ls = report["latency_summary"]
        lines.append(f"## Latency: mean={ls['mean_ms']:.0f}ms, min={ls['min_ms']:.0f}ms, max={ls['max_ms']:.0f}ms")
        lines.append("")

    lines.append("## Decision Trace")
    for step in report["decision_trace"]:
        lines.append(f"### Turn {step['turn']}")
        lines.append(f"- **User:** {step['user_message']}")
        lines.append(f"- **Intent:** `{step['classified_intent']}`")
        lines.append(f"- **Agents:** {', '.join(step['agents_invoked']) or 'none'}")
        lines.append(f"- **Latency:** {step['latency_ms']:.0f}ms" if step['latency_ms'] else "- **Latency:** N/A")
        lines.append(f"- **Response:** {step['response_preview']}...")
        lines.append("")

    if report.get("user_feedback"):
        lines.append("## User Feedback")
        for fb in report["user_feedback"]:
            emoji = "👍" if fb["rating"] == "up" else "👎"
            lines.append(f"- {emoji} {fb.get('comment', 'No comment')}")

    return "\n".join(lines)
