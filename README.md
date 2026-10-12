# AURA — Agentic Unified Retail Assistant for Omni-Channel Commerce

> **A college capstone prototype implementing a hierarchical multi-agent retail system with dynamic task decomposition, short/long-term memory, hybrid recommendations, and decision explainability.**

---

## 📖 Overview

**AURA** is an intelligent, conversational retail assistant designed to handle end-to-end customer commerce journeys across multiple simulated channels (Web, Mobile, WhatsApp, and In-Store Kiosk). 

Built on a hierarchical multi-agent architecture using **LangGraph**, AURA routes customer inquiries through a specialized pipeline:
1. **Coordinator:** Classifies intent and separates single-turn queries from complex multi-part tasks.
2. **Supervisor & Planner:** Breaks compound requests into ordered subtasks and directs state transitions.
3. **Specialized Domain Agents:** Independent nodes that execute targeted tasks using restricted tool sets:
   - 🛍️ **Sales Agent:** Product discovery, attribute filtering, and price queries.
   - ⭐ **Recommendation Agent:** Hybrid suggestions combining catalog TF-IDF similarity with user-item purchase co-occurrence.
   - 📦 **Inventory Agent:** Real-time stock checks across multi-warehouse locations.
   - 💳 **Payment Agent:** Mocked transaction verification and checkout ledger updates.
   - 🚚 **Fulfillment Agent:** Mocked logistics dispatch and shipment scheduling.
   - 🎁 **Loyalty Agent:** Rewards points balance, tier perks, and point redemptions.
   - 🔄 **Post-Purchase Agent:** Order tracking, returns, and policy question-answering via RAG.
4. **Output Composer:** Synthesizes outputs from multiple subagents into a unified, coherent response tailored to the active channel.

---

## 🏗️ Architecture

```mermaid
flowchart TD
    Customer([Customer Query]) --> Coordinator{Coordinator Router}
    
    Coordinator -->|General FAQ / Greeting| DirectResponse[Direct Response]
    Coordinator -->|Single Intent| Supervisor[Supervisor Agent]
    Coordinator -->|Multi-Part Request| Planner[Planner Agent]
    
    Planner -->|Subtask Sequence| Supervisor
    
    Supervisor --> Sales[Sales Agent]
    Supervisor --> Recommender[Recommendation Agent]
    Supervisor --> Inventory[Inventory Agent]
    Supervisor --> Payment[Payment Agent (Mocked)]
    Supervisor --> Fulfillment[Fulfillment Agent (Mocked)]
    Supervisor --> Loyalty[Loyalty Agent]
    Supervisor --> PostPurchase[Post-Purchase Agent]
    
    Sales --> Tools[(Catalog & Product Tools)]
    Recommender --> ML[(Hybrid ML Engine)]
    Inventory --> InvDB[(Warehouse Stock DB)]
    PostPurchase --> RAG[(Vector Policy RAG)]
    
    Sales --> Composer[Output Composer]
    Recommender --> Composer
    Inventory --> Composer
    Payment --> Composer
    Fulfillment --> Composer
    Loyalty --> Composer
    PostPurchase --> Composer
    
    Composer --> AgentLog[(Audit & Trace Logs)]
    Composer --> Response([Omni-Channel Customer Response])
```

---

## 💻 Tech Stack

- **Backend:** Python 3.11, FastAPI, LangGraph (`StateGraph`), LangChain tool-calling.
- **LLM Integrations:** Provider-agnostic via `app/llm.py` (`Groq`, `OpenAI`, `Anthropic`).
- **Database & Persistence:** SQLite + SQLAlchemy ORM (`aura.db`).
- **Vector Retrieval & RAG:** In-memory TF-IDF vector search and cosine similarity over store policies (`policies.json`).
- **Machine Learning Recommendations:** Scikit-learn (TF-IDF item-content similarity + collaborative filtering order co-occurrence pass).
- **Frontend:** React 18, Vite, Lucide React icons.
- **Analytics & Explainability Dashboard:** Streamlit, Matplotlib, Pandas.
- **Packaging & Deployment:** Docker, Docker Compose.

---

## 📁 Repository Layout

```
aura/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI server & REST API
│   │   ├── llm.py                   # Provider-agnostic LLM factory
│   │   ├── state.py                 # Shared AuraState schema
│   │   ├── graph.py                 # LangGraph StateGraph workflow
│   │   ├── agents/                  # Specialized LangGraph nodes
│   │   │   ├── coordinator.py
│   │   │   ├── supervisor.py
│   │   │   ├── planner.py
│   │   │   ├── sales.py
│   │   │   ├── recommendation.py
│   │   │   ├── inventory.py
│   │   │   ├── payment.py
│   │   │   ├── fulfillment.py
│   │   │   ├── loyalty.py
│   │   │   ├── post_purchase.py
│   │   │   └── output_composer.py
│   │   ├── memory/                  # Short-term buffer & vector search
│   │   │   ├── short_term.py
│   │   │   └── vector_store.py
│   │   ├── tools/                   # Agent tool functions
│   │   │   ├── product_tools.py
│   │   │   ├── inventory_tools.py
│   │   │   ├── order_tools.py
│   │   │   ├── payment_tools.py
│   │   │   ├── loyalty_tools.py
│   │   │   └── rag_tools.py
│   │   ├── db/                      # SQLAlchemy models & SQLite session
│   │   │   ├── models.py
│   │   │   └── session.py
│   │   ├── data/                    # Catalogs, policies, and seed script
│   │   │   ├── seed_products.json
│   │   │   ├── seed_customers.json
│   │   │   ├── seed_orders.json
│   │   │   ├── policies.json
│   │   │   └── seed.py
│   │   ├── ml/                      # Hybrid recommender engine
│   │   │   └── recommender.py
│   │   └── evaluation/              # Latency, routing accuracy, traces
│   │       ├── metrics.py
│   │       ├── routing_eval.py
│   │       └── explainability.py
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/                        # React + Vite chat widget
├── dashboard/                       # Streamlit analytics & explainability
│   └── app.py
├── docs/                            # Capstone documentation
│   ├── demo_script.md
│   └── limitations.md
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start

### 1. Configure Environment Variables
Copy `backend/.env.example` to `backend/.env` and set your preferred LLM provider:
```bash
cp backend/.env.example backend/.env
```
Example configuration using Groq:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_groq_api_key_here
MODEL_NAME=llama-3.3-70b-versatile
```

### 2. Run with Docker Compose (Recommended)
Launch all three services simultaneously:
```bash
docker compose up --build
```
- **React Chat Widget:** http://localhost:5173
- **FastAPI API & Docs:** http://localhost:8000/docs
- **Streamlit Analytics Dashboard:** http://localhost:8501

---

### 3. Run Manually (Local Development)

#### Backend Setup:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.data.seed         # Seeds products, customers, orders, policies
uvicorn app.main:app --reload --port 8000
```

#### Frontend Setup:
```bash
cd frontend
npm install
npm run dev
```

#### Dashboard Setup:
```bash
streamlit run dashboard/app.py --server.port 8501
```

---

## 📊 Analytics & Decision Explainability

AURA includes a built-in **Streamlit Dashboard** that tracks:
1. **Latency & Performance:** Mean, median, P95, and max response times per turn.
2. **Intent & Agent Utilization:** Breakdown of customer requests and tool invocations.
3. **Omni-Channel Distribution:** Volume across Web, Mobile, WhatsApp, and Kiosk simulations.
4. **Interactive Decision Traces:** Step-by-step transparency into why a subagent was selected, its input parameters, and its execution latency.
5. **Coordinator Evaluation Suite:** Benchmark harness evaluating routing accuracy across 20 ground-truth test cases across 8 intents.

---

## 🧪 Testing & Verification

Run backend unit and agent tests:
```bash
# Test specific agents
python backend/test_sales.py
python backend/test_inventory.py

# Run all agent integration tests
python backend/test_all_agents.py

# Run routing evaluation
python -c "from app.evaluation.routing_eval import run_routing_eval; print(run_routing_eval())"
```

---

## 📚 Additional Documentation

- [Live Demo Script](docs/demo_script.md) — Step-by-step demo queries and expected behaviors.
- [Prototype Limitations & Future Work](docs/limitations.md) — Detailed review of Phase-1 academic assumptions vs. production retail systems.

---

## 📄 License
Academic Capstone Project — Developed for educational demonstration purposes.
