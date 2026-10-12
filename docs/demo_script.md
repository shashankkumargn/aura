# AURA Live Demonstration Script

This document provides a step-by-step walkthrough for evaluating and demonstrating **AURA (Agentic Unified Retail Assistant for Omni-Channel Commerce)**.

---

## 1. Prerequisites & Setup

### 1.1 Environment Configuration
Ensure your `.env` file exists in `backend/.env` with your active LLM provider credentials:
```env
LLM_PROVIDER=groq     # or "openai" | "anthropic"
GROQ_API_KEY=your_api_key_here
MODEL_NAME=llama-3.3-70b-versatile
```

### 1.2 Start Services

#### Option A: Docker Compose (All Services)
```bash
docker compose up --build
```
- **Frontend Chat Widget:** http://localhost:5173
- **FastAPI Backend:** http://localhost:8000 (Docs at http://localhost:8000/docs)
- **Analytics & Explainability Dashboard:** http://localhost:8501

#### Option B: Local Development
**Terminal 1 — Backend:**
```bash
cd backend
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
python -m app.data.seed
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm install
npm run dev
```

**Terminal 3 — Dashboard:**
```bash
streamlit run dashboard/app.py --server.port 8501
```

---

## 2. Demo Persona & Seed State

The database comes pre-seeded with test accounts and order history:
- **Customer:** `u123` (Alex Sharma)
  - **Tier:** Gold
  - **Loyalty Points:** 450
  - **Orders:**
    - `ORD-1001`: Shipped, In-Transit (Audio product)
    - `ORD-1002`: Delivered 6 days ago (Eligible for standard 7-day return)

---

## 3. Step-by-Step Scenario Walkthrough

### Scenario 1: Initial Greeting & General FAQ
- **Channel:** `web`
- **User Prompt:**
  ```text
  Hello! What can you help me with today?
  ```
- **What to Observe:**
  - **Coordinator** classifies intent as `general_faq`.
  - Assistant responds directly with an overview of services (product search, order tracking, recommendations, returns, loyalty).
  - No subagent tools needed.

---

### Scenario 2: Product Discovery & Catalog Search (Sales Agent)
- **User Prompt:**
  ```text
  Show me wireless earphones under 2000
  ```
- **What to Observe:**
  - **Coordinator** detects `product_search`.
  - **Supervisor** activates the **Sales Agent**.
  - Sales Agent invokes `search_products(query="wireless earphones", max_price=2000)`.
  - Returns catalog items (e.g., boAt, Boult, Realme) with exact prices in INR and stock status.

---

### Scenario 3: Real-Time Stock & Warehouse Inventory (Inventory Agent)
- **User Prompt:**
  ```text
  Is the boAt Wireless Neckband Earphones in stock? Check product P001.
  ```
- **What to Observe:**
  - **Coordinator** routes to `inventory`.
  - **Supervisor** invokes **Inventory Agent**.
  - Inventory Agent calls `check_stock(product_id="P001")`.
  - Reports current stock quantity and warehouse location (`warehouse_blr_01`).

---

### Scenario 4: AI Recommendations & Hybrid Filtering (Recommendation Agent)
- **User Prompt:**
  ```text
  Recommend a good smartwatch for fitness and workouts.
  ```
- **What to Observe:**
  - **Coordinator** routes to `recommendation`.
  - **Recommendation Agent** executes `get_personalized_recommendations` combining collaborative filtering and TF-IDF similarity.
  - Suggests models from the catalog matching fitness profiles (e.g., Noise, Amazfit, Fire-Boltt).

---

### Scenario 5: Multi-Part Request & Decomposition (Planner + Supervisor)
- **User Prompt:**
  ```text
  Check if product P002 is in stock, and also check how many loyalty points I have.
  ```
- **What to Observe:**
  - **Coordinator** detects a composite query.
  - **Planner Agent** breaks the prompt into sub-tasks:
    1. Inventory check on `P002`.
    2. Loyalty points query for `u123`.
  - **Supervisor** executes each task sequentially and **Output Composer** synthesizes a unified answer.

---

### Scenario 6: Order Tracking & Status (Post-Purchase Agent)
- **User Prompt:**
  ```text
  Where is my order ORD-1001?
  ```
- **What to Observe:**
  - **Coordinator** classifies as `order_status`.
  - **Post-Purchase Agent** calls `track_order(order_id="ORD-1001")`.
  - Returns shipment status (`in_transit`), courier details, and estimated delivery window.

---

### Scenario 7: Returns, Refunds & Policy RAG (Post-Purchase Agent)
- **User Prompt:**
  ```text
  I want to return order ORD-1002. Can I get a full refund?
  ```
- **What to Observe:**
  - **Coordinator** routes to `return_or_complaint`.
  - **Post-Purchase Agent** uses `rag_search` to query store return policies from `policies.json`.
  - Verifies that `ORD-1002` was delivered 6 days ago (within the 7-day window).
  - Initiates return request or guides user on refund eligibility.

---

### Scenario 8: Loyalty Points & Rewards Redemption (Loyalty Agent)
- **User Prompt:**
  ```text
  How many reward points do I have and what tier am I?
  ```
- **What to Observe:**
  - **Loyalty Agent** calls `get_loyalty_balance(customer_id="u123")`.
  - Confirms 450 points, Gold Tier status, and available redemption benefits.

---

### Scenario 9: Mock Checkout & Simulated Payment (Payment Agent)
- **User Prompt:**
  ```text
  I want to pay 1499 for my order using UPI.
  ```
- **What to Observe:**
  - **Payment Agent** invokes `process_payment(order_id="ORD-1001", amount=1499, method="upi")`.
  - Returns simulated transaction ID (`TXN-...`) and marks payment status as `completed`.

---

### Scenario 10: Omnichannel Simulation
- Test how AURA adapts to different simulated channels:
  - **Web Chat:** Default rich text formatting with quick buttons.
  - **WhatsApp Simulation (`whatsapp_sim`):** Concise, emoji-rich messages formatted for chat messaging apps.
  - **Kiosk Simulation (`kiosk_sim`):** Direct, touch-friendly prompts formatted for in-store displays.

---

## 4. Analytics & Explainability Dashboard Demonstration

Open http://localhost:8501 in your browser:

1. **Top KPI Row:** Review total turns, unique sessions, mean and P95 latency.
2. **Performance Tab:** Inspect latency trends and the slowest turns table.
3. **Agent Utilization Tab:** View the bar charts for intent distributions and specialized agent invocations.
4. **Explainability & Decision Traces:**
   - Select your active `session_id` from the dropdown.
   - Expand any turn to view the exact classified intent, subagents triggered, latency, and response text.
   - Click **Download Trace as Markdown** to export the audit log.
5. **Coordinator Evaluation Tab:**
   - Click **Run Coordinator Benchmark Evaluation**.
   - Watch the 20 ground-truth test cases run and verify accuracy across the 8 intents.
6. **User Feedback Tab:** Submit thumbs up/down in the chat UI and verify they appear instantly in the dashboard feedback audit table.
