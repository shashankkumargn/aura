"""Seed realistic conversation logs and feedback for the AURA dashboard.

Populates aura.db with multi-turn sessions, realistic latencies, agent traces,
omnichannel distributions, and user ratings so the evaluation dashboard reflects
comprehensive system telemetry.
"""

from __future__ import annotations

import datetime
import json
import random
from pathlib import Path

from app.db.models import AgentLog, Feedback
from app.db.session import SessionLocal, init_db

DEMO_SESSIONS = [
    {
        "session_id": "sess_audio_hunt",
        "user_id": "u123",
        "channel": "web",
        "turns": [
            {
                "user_message": "Show me wireless earphones under 2000",
                "intent": "product_search",
                "agents_used": ["coordinator", "supervisor", "sales"],
                "latency_ms": 1420.5,
                "final_response": "Here are our top-rated wireless earphones under ₹2,000:\n• boAt Wireless Neckband Earphones (₹899) - In Stock\n• Boult True Wireless Stereo Earbuds (₹1,299) - In Stock\n• Realme Magnetic Neckband (₹1,499) - In Stock",
                "feedback": {"rating": "up", "comment": "Fast and found exact products within my budget!"},
            },
            {
                "user_message": "Is the boAt neckband available in Bangalore warehouse? Check P001.",
                "intent": "inventory",
                "agents_used": ["coordinator", "supervisor", "inventory"],
                "latency_ms": 980.2,
                "final_response": "Yes! boAt Wireless Neckband (P001) has 32 units available at Bangalore Main Hub (warehouse_blr_01). Standard 2-day delivery is available.",
                "feedback": {"rating": "up", "comment": "Great real-time stock check."},
            },
        ],
    },
    {
        "session_id": "sess_smartwatch_rec",
        "user_id": "u123",
        "channel": "mobile",
        "turns": [
            {
                "user_message": "Recommend a good smartwatch for marathon training and fitness",
                "intent": "recommendation",
                "agents_used": ["coordinator", "supervisor", "recommendation"],
                "latency_ms": 1850.0,
                "final_response": "Based on fitness tracking profiles and collaborative purchase history, we recommend:\n1. Noise Fitness Smart Band (AMOLED Display, ₹1,899)\n2. Amazfit Rugged Outdoor Smartwatch (Built-in GPS, ₹3,999)\n3. Fire-Boltt Bluetooth Calling Watch (₹1,499)",
                "feedback": {"rating": "up", "comment": "Very relevant recommendations."},
            },
            {
                "user_message": "Compare the battery life between Noise and Amazfit",
                "intent": "recommendation",
                "agents_used": ["coordinator", "supervisor", "recommendation"],
                "latency_ms": 1390.4,
                "final_response": "Comparison:\n• Noise Fitness Band: 14 days typical battery life, lightweight for sleep tracking.\n• Amazfit Rugged: 21 days battery with military-grade power management and continuous GPS tracking.",
                "feedback": {"rating": "up", "comment": "Clear comparison table."},
            },
        ],
    },
    {
        "session_id": "sess_order_track",
        "user_id": "u123",
        "channel": "whatsapp_sim",
        "turns": [
            {
                "user_message": "Where is my order ORD-1001?",
                "intent": "order_status",
                "agents_used": ["coordinator", "supervisor", "post_purchase"],
                "latency_ms": 860.1,
                "final_response": "📦 Your order ORD-1001 is in transit with BlueDart!\n• Courier AWB: BD-9823101\n• Status: Out for delivery in Bangalore\n• ETA: Today by 5:00 PM.",
                "feedback": {"rating": "up", "comment": "Accurate tracking info."},
            },
        ],
    },
    {
        "session_id": "sess_return_refund",
        "user_id": "u123",
        "channel": "web",
        "turns": [
            {
                "user_message": "I received order ORD-1002 6 days ago. Can I return it for a full refund?",
                "intent": "return_or_complaint",
                "agents_used": ["coordinator", "supervisor", "post_purchase"],
                "latency_ms": 1720.6,
                "final_response": "Under our 7-Day Return Policy, your order ORD-1002 (delivered 6 days ago) is fully eligible for a full refund! I have generated Return Request #RET-8941. Our courier will pick up the package tomorrow.",
                "feedback": {"rating": "up", "comment": "Super hassle-free return policy."},
            },
        ],
    },
    {
        "session_id": "sess_composite_request",
        "user_id": "user1",
        "channel": "web",
        "turns": [
            {
                "user_message": "Check if product P002 is in stock, and also check how many reward points I have",
                "intent": "product_search",
                "agents_used": ["coordinator", "planner", "supervisor", "inventory", "loyalty", "output_composer"],
                "latency_ms": 2490.8,
                "final_response": "1. Inventory: Product P002 (True Wireless Earbuds) has 24 units in stock.\n2. Loyalty Balance: You currently have 180 Silver tier points (worth ₹90 discount on your next checkout).",
                "feedback": {"rating": "up", "comment": "Handled both questions in one prompt!"},
            },
        ],
    },
    {
        "session_id": "sess_kiosk_touch",
        "user_id": "CUST-005",
        "channel": "kiosk_sim",
        "turns": [
            {
                "user_message": "Where can I find running shoes in this store?",
                "intent": "product_search",
                "agents_used": ["coordinator", "supervisor", "sales"],
                "latency_ms": 780.0,
                "final_response": "Running shoes are located in Aisle 4 (Footwear Section). We currently have Nike Mesh Running Shoes (₹899) and Puma Pro Grip Trainers (₹1,499) on display.",
                "feedback": {"rating": "up", "comment": "Very helpful for in-store navigation."},
            },
        ],
    },
    {
        "session_id": "sess_loyalty_redeem",
        "user_id": "u123",
        "channel": "web",
        "turns": [
            {
                "user_message": "How many points do I have and can I redeem 200 points?",
                "intent": "loyalty",
                "agents_used": ["coordinator", "supervisor", "loyalty"],
                "latency_ms": 1150.3,
                "final_response": "You currently hold 450 Gold tier points. You can redeem 200 points for an instant ₹100 discount coupon on your next order. Would you like me to generate the promo code?",
                "feedback": {"rating": "up", "comment": "Clear points explanation."},
            },
        ],
    },
    {
        "session_id": "sess_checkout_payment",
        "user_id": "u123",
        "channel": "mobile",
        "turns": [
            {
                "user_message": "Pay 1499 for my order using UPI",
                "intent": "payment",
                "agents_used": ["coordinator", "supervisor", "payment"],
                "latency_ms": 1050.4,
                "final_response": "Payment of ₹1,499 for ORD-1001 has been simulated successfully!\n• Transaction ID: TXN-UPI-99214\n• Status: Completed\n• Payment Method: UPI",
                "feedback": {"rating": "up", "comment": "Instant checkout confirmation."},
            },
        ],
    },
    {
        "session_id": "sess_general_greeting",
        "user_id": "CUST-012",
        "channel": "web",
        "turns": [
            {
                "user_message": "Hello! What can you help me with?",
                "intent": "general_faq",
                "agents_used": ["coordinator"],
                "latency_ms": 620.5,
                "final_response": "Hello! I am AURA, your Omnichannel Retail Assistant. I can help you search products, check warehouse stock, track orders, process returns, recommend items, and manage loyalty points.",
                "feedback": None,
            },
        ],
    },
]

# Additional synthetic background turns to build realistic distributions
CHANNELS = ["web", "mobile", "whatsapp_sim", "kiosk_sim"]
CHANNEL_WEIGHTS = [0.45, 0.30, 0.15, 0.10]

INTENTS_POOL = [
    ("product_search", ["coordinator", "supervisor", "sales"], 1250, 400),
    ("recommendation", ["coordinator", "supervisor", "recommendation"], 1750, 500),
    ("inventory", ["coordinator", "supervisor", "inventory"], 950, 250),
    ("order_status", ["coordinator", "supervisor", "post_purchase"], 880, 200),
    ("payment", ["coordinator", "supervisor", "payment"], 1100, 300),
    ("loyalty", ["coordinator", "supervisor", "loyalty"], 1050, 250),
    ("return_or_complaint", ["coordinator", "supervisor", "post_purchase"], 1600, 450),
    ("general_faq", ["coordinator"], 650, 150),
]


def seed_logs_and_feedback(total_extra_turns: int = 50) -> None:
    """Populate database with rich logs and feedback."""
    init_db()
    db = SessionLocal()

    try:
        # Wipe existing logs for clean presentation
        db.query(AgentLog).delete()
        db.query(Feedback).delete()
        db.commit()

        now = datetime.datetime.utcnow()
        turn_count = 0

        # 1. Seed structured demo sessions
        for s in DEMO_SESSIONS:
            s_id = s["session_id"]
            u_id = s["user_id"]
            ch = s["channel"]
            base_time = now - datetime.timedelta(hours=random.randint(2, 48))

            for idx, turn in enumerate(s["turns"]):
                timestamp = base_time + datetime.timedelta(minutes=idx * 2)
                log = AgentLog(
                    session_id=s_id,
                    user_id=u_id,
                    channel=ch,
                    user_message=turn["user_message"],
                    intent=turn["intent"],
                    agents_used=json.dumps(turn["agents_used"]),
                    latency_ms=turn["latency_ms"],
                    final_response=turn["final_response"],
                    timestamp=timestamp,
                )
                db.add(log)
                turn_count += 1

                if turn.get("feedback"):
                    fb = Feedback(
                        session_id=s_id,
                        rating=turn["feedback"]["rating"],
                        comment=turn["feedback"]["comment"],
                        timestamp=timestamp + datetime.timedelta(seconds=20),
                    )
                    db.add(fb)

        db.commit()

        # 2. Seed realistic historical baseline turns
        sample_queries = {
            "product_search": "Search for noise cancelling headphones under 5000",
            "recommendation": "What are best selling smart bands?",
            "inventory": "Check stock for P005",
            "order_status": "Track my shipment ORD-1045",
            "payment": "Pay invoice using credit card",
            "loyalty": "Show my loyalty points",
            "return_or_complaint": "Need refund on defective charger",
            "general_faq": "What are store opening hours?",
        }

        for i in range(total_extra_turns):
            days_ago = random.uniform(0.1, 7.0)
            t_stamp = now - datetime.timedelta(days=days_ago)
            s_id = f"sess_hist_{random.randint(100, 999)}"
            u_id = f"CUST-{random.randint(1, 40):03d}"
            ch = random.choices(CHANNELS, weights=CHANNEL_WEIGHTS)[0]

            intent_info = random.choice(INTENTS_POOL)
            intent, agents, mean_lat, std_lat = intent_info
            lat = max(450.0, round(random.gauss(mean_lat, std_lat), 1))

            query_text = sample_queries.get(intent, "Help me with retail items")

            log = AgentLog(
                session_id=s_id,
                user_id=u_id,
                channel=ch,
                user_message=query_text,
                intent=intent,
                agents_used=json.dumps(agents),
                latency_ms=lat,
                final_response=f"Automated resolution generated by AURA specialized agents ({', '.join(agents)}).",
                timestamp=t_stamp,
            )
            db.add(log)
            turn_count += 1

            # Random feedback on ~30% of turns (mostly positive)
            if random.random() < 0.35:
                rating = "up" if random.random() > 0.12 else "down"
                comment = "Very fast response" if rating == "up" else "Could be more detailed"
                fb = Feedback(
                    session_id=s_id,
                    rating=rating,
                    comment=comment,
                    timestamp=t_stamp + datetime.timedelta(seconds=15),
                )
                db.add(fb)

        db.commit()

        total_logs = db.query(AgentLog).count()
        total_fb = db.query(Feedback).count()
        print(f"SUCCESS: Seeded {total_logs} agent logs and {total_fb} user feedbacks into aura.db!")

    finally:
        db.close()


if __name__ == "__main__":
    seed_logs_and_feedback(55)
