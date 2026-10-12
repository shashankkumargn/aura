"""AURA Analytics and Explainability Dashboard.

Streamlit-based dashboard providing real-time visibility into multi-agent
orchestration, latency metrics, routing distribution, explainability traces,
live sandbox querying, and coordinator evaluation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure backend modules can be imported and prevent dashboard/app.py from colliding with backend/app
DASHBOARD_DIR = Path(__file__).resolve().parent
BACKEND_DIR = DASHBOARD_DIR.parent / "backend"

sys.path = [p for p in sys.path if Path(p).resolve() != DASHBOARD_DIR]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

import urllib.request
import streamlit as st

from app.db.models import AgentLog, Feedback
from app.db.session import SessionLocal, init_db
from app.evaluation.explainability import (
    build_explainability_report,
    format_trace_markdown,
    get_decision_trace,
)
from app.evaluation.metrics import (
    compute_agent_utilization,
    compute_channel_distribution,
    compute_intent_distribution,
    compute_latency_stats,
)
from app.evaluation.routing_eval import ROUTING_TEST_CASES, run_routing_eval

try:
    init_db()
except Exception:
    pass


def inject_custom_styles() -> None:
    """Inject modern executive dark-mode styling."""
    st.markdown(
        """
        <style>
        /* Modern dashboard styling */
        .main-header {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 24px 28px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }
        .header-title {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(90deg, #60a5fa 0%, #a78bfa 50%, #f472b6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }
        .header-subtitle {
            color: #94a3b8;
            font-size: 0.95rem;
            margin-bottom: 0px;
        }
        .metric-card {
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.07);
            padding: 18px 20px;
            border-radius: 12px;
            backdrop-filter: blur(8px);
        }
        .badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .badge-intent { background: #312e81; color: #a5b4fc; }
        .badge-agent { background: #064e3b; color: #6ee7b7; }
        .badge-channel { background: #701a75; color: #f0abfc; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_db_summary(limit: int = 200) -> dict:
    """Retrieve summary metrics and logs from aura.db."""
    db = SessionLocal()
    try:
        total_logs = db.query(AgentLog).count()
        logs = (
            db.query(AgentLog)
            .order_by(AgentLog.timestamp.desc())
            .limit(limit)
            .all()
        )
        unique_sessions = len(set(l.session_id for l in logs if l.session_id))

        feedbacks = db.query(Feedback).order_by(Feedback.timestamp.desc()).all()
        up_count = sum(1 for f in feedbacks if f.rating == "up")
        down_count = sum(1 for f in feedbacks if f.rating == "down")
        total_fb = len(feedbacks)
        satisfaction = round((up_count / total_fb * 100), 1) if total_fb > 0 else 100.0

        return {
            "total_logs": total_logs,
            "unique_sessions": unique_sessions,
            "recent_logs": logs,
            "feedbacks": feedbacks,
            "up_count": up_count,
            "down_count": down_count,
            "satisfaction": satisfaction,
        }
    finally:
        db.close()


def send_live_chat_query(message: str, channel: str = "web") -> dict | None:
    """Send query to the live FastAPI backend at http://localhost:8000/chat."""
    try:
        url = "http://localhost:8000/chat"
        payload = json.dumps({
            "session_id": "dashboard_live_demo",
            "channel": channel,
            "user_id": "u123",
            "message": message,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def main() -> None:
    st.set_page_config(
        page_title="AURA — Analytics & Explainability",
        page_icon="🛍️",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_custom_styles()

    # Hero Header Banner
    st.markdown(
        """
        <div class="main-header">
            <div class="header-title">🛍️ AURA Analytics & Explainability</div>
            <div class="header-subtitle">
                Agentic Unified Retail Assistant for Omni-Channel Commerce &nbsp;•&nbsp; 
                Hierarchical Multi-Agent System Telemetry & Evaluation
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar Controls & Live Query Sandbox
    st.sidebar.header("⚙️ Telemetry Controls")
    log_limit = st.sidebar.slider("Audit Window (Last N Turns)", min_value=10, max_value=500, value=150, step=10)

    if st.sidebar.button("🔄 Refresh Telemetry", use_container_width=True):
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🧪 Live Multi-Agent Sandbox")
    st.sidebar.caption("Send a query directly to the live backend (:8000) and watch telemetry update in real-time:")

    sandbox_channel = st.sidebar.selectbox("Simulated Channel:", ["web", "mobile", "whatsapp_sim", "kiosk_sim"])
    sandbox_input = st.sidebar.text_input("Enter Query:", placeholder="e.g., Show me wireless earphones under 2000")

    quick_prompts = [
        "Show me wireless earphones under 2000",
        "Is the boAt neckband P001 in stock?",
        "Where is my order ORD-1001?",
        "Recommend smartwatches for running",
        "How many loyalty points do I have?",
    ]

    selected_prompt = st.sidebar.selectbox("Or Pick a Test Prompt:", ["(Select sample...)"] + quick_prompts)

    query_to_send = sandbox_input if sandbox_input else (selected_prompt if selected_prompt != "(Select sample...)" else None)

    if st.sidebar.button("🚀 Execute Query via AURA", type="primary", use_container_width=True):
        if query_to_send:
            with st.spinner(f"Routing through Coordinator & Specialized Agents..."):
                res = send_live_chat_query(query_to_send, channel=sandbox_channel)
                if res and "error" not in res:
                    st.sidebar.success("Turn Executed Successfully!")
                    st.sidebar.markdown(f"**Intent:** `{res.get('intent')}`")
                    st.sidebar.markdown(f"**Agents:** `{', '.join(res.get('agents_used', []))}`")
                    st.sidebar.info(res.get("response", ""))
                    st.rerun()
                else:
                    st.sidebar.error(f"Execution Error: {res.get('error', 'Backend unreachable')}")
        else:
            st.sidebar.warning("Please type a message or select a prompt.")

    st.sidebar.markdown("---")
    st.sidebar.subheader("System Architecture")
    st.sidebar.markdown(
        """
        - **Orchestration:** LangGraph `StateGraph`
        - **Core Nodes:** Coordinator, Supervisor, Planner
        - **Subagents:** Sales, Recommender, Inventory, Payment, Fulfillment, Loyalty, Post-Purchase
        - **Composer:** Channel-adapted Output Composer
        """
    )

    # Fetch Metrics
    summary = get_db_summary(limit=log_limit)
    latency_stats = compute_latency_stats(limit=log_limit)

    # Top KPI Metrics Cards
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric(label="Total Processed Turns", value=summary["total_logs"], delta="Live Stream")
    with k2:
        st.metric(label="Tracked Sessions", value=summary["unique_sessions"])
    with k3:
        st.metric(
            label="Mean Turn Latency",
            value=f"{latency_stats['mean_ms']:.0f} ms" if latency_stats["count"] > 0 else "N/A",
            delta=f"{latency_stats['median_ms']:.0f} ms median",
            delta_color="off",
        )
    with k4:
        st.metric(
            label="P95 Peak Latency",
            value=f"{latency_stats['p95_ms']:.0f} ms" if latency_stats["count"] > 0 else "N/A",
            delta=f"Max {latency_stats['max_ms']:.0f} ms",
            delta_color="inverse",
        )
    with k5:
        st.metric(
            label="User Satisfaction",
            value=f"{summary['satisfaction']}%",
            delta=f"{summary['up_count']} 👍 / {summary['down_count']} 👎",
        )

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # Main Dashboard Tabs
    tab_latency, tab_agents, tab_trace, tab_eval, tab_feedback = st.tabs([
        "⚡ Latency & SLA Performance",
        "🧭 Agent Utilization & Routing",
        "🔍 Explainability & Decision Traces",
        "🎯 Coordinator Accuracy Evaluation",
        "💬 User Feedback & Audit Logs",
    ])

    # ---------------- TAB 1: LATENCY & PERFORMANCE ----------------
    with tab_latency:
        st.subheader("Turn Execution Latency & SLA Breakdown")

        if latency_stats["count"] == 0:
            st.info("No latency logs available yet. Use the sidebar sandbox or chat widget to generate turns.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mean Latency", f"{latency_stats['mean_ms']} ms")
            c2.metric("Median Latency", f"{latency_stats['median_ms']} ms")
            c3.metric("P95 Latency", f"{latency_stats['p95_ms']} ms")
            c4.metric("Max Recorded", f"{latency_stats['max_ms']} ms")

            st.markdown("#### Chronological Latency Sequence")
            valid_logs = [l for l in summary["recent_logs"] if l.latency_ms is not None]
            if len(valid_logs) > 1:
                chart_data = {
                    f"Turn {len(valid_logs) - idx}": round(l.latency_ms, 1)
                    for idx, l in enumerate(reversed(valid_logs))
                }
                st.line_chart(chart_data)
            else:
                st.info("Only 1 log entry present. Run more queries from the sidebar to populate the trend.")

            st.markdown("#### Latency Tier Distribution")
            fast = sum(1 for l in valid_logs if l.latency_ms < 1000)
            medium = sum(1 for l in valid_logs if 1000 <= l.latency_ms < 2000)
            slow = sum(1 for l in valid_logs if l.latency_ms >= 2000)
            st.bar_chart({"< 1.0s (Fast)": fast, "1.0s - 2.0s (Normal)": medium, "≥ 2.0s (Composite/RAG)": slow})

            st.markdown("#### Top Slowest Query Traces")
            slowest = sorted(valid_logs, key=lambda x: x.latency_ms, reverse=True)[:5]
            if slowest:
                slowest_data = [
                    {
                        "Session ID": l.session_id,
                        "Intent": l.intent,
                        "Latency (ms)": f"{l.latency_ms:.0f}",
                        "Agents Dispatched": l.agents_used,
                        "User Message": (l.user_message or "")[:70],
                    }
                    for l in slowest
                ]
                st.dataframe(slowest_data, use_container_width=True)

    # ---------------- TAB 2: AGENT UTILIZATION & ROUTING ----------------
    with tab_agents:
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Intent Classification Volume")
            intents = compute_intent_distribution(limit=log_limit)
            if intents:
                st.bar_chart(intents)
                st.caption("Distribution of customer queries classified across the 8 domain intents.")
            else:
                st.info("No intent records found.")

            st.subheader("Omnichannel Traffic (Simulated)")
            channels = compute_channel_distribution(limit=log_limit)
            if channels:
                st.bar_chart(channels)
                st.caption("Message volume by channel metadata tag.")
            else:
                st.info("No channel data found.")

        with col_right:
            st.subheader("Specialized Agent Invocations")
            agents = compute_agent_utilization(limit=log_limit)
            if agents:
                st.bar_chart(agents)
                st.caption("Invocation frequencies for specialized domain subagents dispatched by Supervisor.")
            else:
                st.info("No agent invocation logs found.")

    # ---------------- TAB 3: EXPLAINABILITY & DECISION TRACE ----------------
    with tab_trace:
        st.subheader("Full Multi-Agent Decision Trace & Explainability")
        st.write("Inspect how the Coordinator, Supervisor, and specialized agents resolved individual turns.")

        recent_sessions = list(dict.fromkeys(l.session_id for l in summary["recent_logs"] if l.session_id))

        if not recent_sessions:
            st.info("No session logs available.")
        else:
            selected_session = st.selectbox("Select Conversation Session to Inspect:", recent_sessions, index=0)

            if selected_session:
                report = build_explainability_report(selected_session)
                if "error" in report:
                    st.error(report["error"])
                else:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Customer ID", report.get("user_id", "N/A"))
                    c2.metric("Channel Used", report.get("channel", "web"))
                    c3.metric("Total Turns", report.get("total_turns", 0))
                    if report.get("latency_summary"):
                        c4.metric("Avg Latency", f"{report['latency_summary']['mean_ms']:.0f} ms")

                    st.markdown("### Step-by-Step Execution Chain")
                    for step in report.get("decision_trace", []):
                        agents_str = ", ".join(step["agents_invoked"]) if step["agents_invoked"] else "Direct Response"
                        lat = f"{step['latency_ms']:.0f} ms" if step['latency_ms'] else "N/A"

                        with st.expander(f"Turn {step['turn']}: '{step['user_message']}'", expanded=True):
                            tc1, tc2, tc3 = st.columns([1, 1, 1])
                            tc1.markdown(f"**Intent Classified:** `{step['classified_intent']}`")
                            tc2.markdown(f"**Agents Dispatched:** `{agents_str}`")
                            tc3.markdown(f"**Turn Latency:** `{lat}`")

                            st.markdown("**Generated Response:**")
                            st.info(step["response_preview"])

                    md_trace = format_trace_markdown(selected_session)
                    st.download_button(
                        label="📥 Download Full Decision Trace as Markdown",
                        data=md_trace,
                        file_name=f"trace_{selected_session}.md",
                        mime="text/markdown",
                    )

    # ---------------- TAB 4: ROUTING ACCURACY EVALUATION ----------------
    with tab_eval:
        st.subheader("Coordinator Routing Accuracy Benchmark")
        st.write(
            f"Run benchmark evaluation across {len(ROUTING_TEST_CASES)} labeled ground-truth test cases covering 8 intents."
        )

        if st.button("🚀 Run Coordinator Benchmark Evaluation", type="primary", use_container_width=True):
            with st.spinner("Running 20 queries through Coordinator agent..."):
                try:
                    eval_results = run_routing_eval()
                    ec1, ec2, ec3 = st.columns(3)
                    ec1.metric("Total Test Cases", eval_results["total"])
                    ec2.metric("Correct Routes", eval_results["correct"])
                    ec3.metric("Routing Accuracy", f"{eval_results['accuracy']}%")

                    st.markdown("#### Per-Intent Accuracy Breakdown")
                    st.table(eval_results["per_intent"])

                    if eval_results["failures"]:
                        st.markdown("#### Misclassified Queries")
                        st.warning(f"{len(eval_results['failures'])} queries routed to unexpected intents:")
                        st.table(eval_results["failures"])
                    else:
                        st.success("All test cases classified accurately! 100% precision.")
                except Exception as ex:
                    st.error(f"Routing evaluation error: {ex}")

    # ---------------- TAB 5: FEEDBACK & RAW LOGS ----------------
    with tab_feedback:
        st.subheader("User Feedback Audit (Human-in-the-Loop)")
        fbs = summary["feedbacks"]
        if not fbs:
            st.info("No feedback entries submitted yet.")
        else:
            fb_rows = [
                {
                    "ID": f.id,
                    "Session ID": f.session_id,
                    "Rating": "👍 Positive" if f.rating == "up" else "👎 Negative",
                    "Comment": f.comment or "—",
                    "Timestamp": f.timestamp.strftime("%Y-%m-%d %H:%M:%S") if f.timestamp else "—",
                }
                for f in fbs
            ]
            st.dataframe(fb_rows, use_container_width=True)

        st.markdown("---")
        st.subheader("Raw Agent Audit Logs")
        if summary["recent_logs"]:
            raw_data = [
                {
                    "ID": l.id,
                    "Session": l.session_id,
                    "Channel": l.channel,
                    "User Message": l.user_message,
                    "Intent": l.intent,
                    "Agents": l.agents_used,
                    "Latency (ms)": l.latency_ms,
                    "Timestamp": l.timestamp.strftime("%Y-%m-%d %H:%M:%S") if l.timestamp else "—",
                }
                for l in summary["recent_logs"]
            ]
            st.dataframe(raw_data, use_container_width=True)
        else:
            st.info("No raw agent logs available.")


if __name__ == "__main__" or "streamlit" in sys.modules:
    main()
