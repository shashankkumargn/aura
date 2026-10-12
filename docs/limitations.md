# AURA Phase-1 Prototype Limitations & Future Work

AURA (**Agentic Unified Retail Assistant for Omni-Channel Commerce**) is developed as a **Phase-1 academic capstone prototype**. It demonstrates multi-agent orchestration, intent classification, dynamic task decomposition, tool-calling, and explainability for retail commerce.

This document outlines the architectural boundaries, prototype trade-offs, and design decisions of the current implementation, along with recommended pathways for production hardening.

---

## 1. Prototype Limitations

### 1.1 Mocked Payment & Financial Transactions
- **Current Behavior:** The `Payment` agent simulates transaction processing by validating order amounts against the SQLite database and returning generated transaction identifiers (`TXN-...`).
- **Production Requirement:** Integration with certified payment gateways (e.g., Stripe, Razorpay, Adyen), PCI-DSS compliance, tokenized card management, Webhook reconciliation, 3D-Secure MFA, and double-entry accounting ledgers.

### 1.2 Mocked Logistics & Fulfillment
- **Current Behavior:** Order fulfillment and delivery statuses (`packed`, `shipped`, `in_transit`, `delivered`) are managed as static states and mocked timeline calculations within the database.
- **Production Requirement:** Direct API integrations with 3PL carriers (e.g., FedEx, BlueDart, Delhivery), automated airway bill (AWB) generation, webhook-driven tracking events, and warehouse management system (WMS) inventory reservations.

### 1.3 Simulated Omni-Channel Communication
- **Current Behavior:** Omnichannel support is simulated using a request-level `channel` tag (`web`, `mobile`, `whatsapp_sim`, `kiosk_sim`). The system adjusts formatting rules and prompt instructions based on this metadata.
- **Production Requirement:** Production Webhook handlers for Meta's WhatsApp Cloud API, Twilio SMS/MMS, mobile push notification dispatchers (FCM/APNs), and native POS kiosk peripheral drivers (barcode scanners, receipt printers).

### 1.4 Vector Search & Embeddings Scope
- **Current Behavior:** Semantic retrieval (`rag_tools.py`) operates via an in-memory TF-IDF vectorizer and cosine similarity across `policies.json` and product catalog attributes.
- **Production Requirement:** High-dimensional dense embeddings (e.g., `text-embedding-3-small`, `all-MiniLM-L6-v2`) backed by a persistent vector database (e.g., FAISS index files, pgvector, Qdrant, or Pinecone) with hybrid dense-sparse search and re-ranking (Cross-Encoders).

### 1.5 Recommendation Engine Scale
- **Current Behavior:** The `ml/recommender.py` module uses a hybrid approach combining item-attribute TF-IDF cosine similarity with a co-occurrence collaborative filtering matrix derived from historical orders.
- **Production Requirement:** Multi-stage retrieval and ranking pipelines (Two-Tower neural networks, DeepFM, or Graph Neural Networks) with real-time user clickstream feature logging and vector candidate generation.

### 1.6 Storage & Concurrency
- **Current Behavior:** Local SQLite database (`aura.db`) with SQLAlchemy ORM.
- **Production Requirement:** Enterprise relational database (e.g., PostgreSQL) with connection pooling (`pgbouncer`), read replicas for analytics queries, and Redis caching for agent session states and rate limiting.

### 1.7 Authentication & Multi-Tenancy
- **Current Behavior:** Requests supply a plain `user_id` (e.g. `u123`) without user authentication, and the database operates in a single-store environment.
- **Production Requirement:** OAuth2 / JWT authentication, role-based access control (RBAC), and schema-level multi-tenant partitioning for multi-store retail platforms.

### 1.8 External LLM Provider Dependency
- **Current Behavior:** Agents rely on external API calls (Groq, OpenAI, or Anthropic). Response latencies typically range from 0.5s to 3.0s depending on network conditions and provider load.
- **Production Requirement:** Fallback chains with local open-weights models (e.g., vLLM with Llama 3 8B / Mistral 7B) for high-availability offline routing and cost optimization.

---

## 2. Summary Matrix: Phase-1 vs. Production

| Capability | AURA Phase-1 Prototype | Production Retail System |
| :--- | :--- | :--- |
| **Multi-Agent Orchestration** | LangGraph StateGraph (Coordinator + Supervisor + Subagents) | LangGraph / Microservices with distributed event buses |
| **Payment Gateway** | Mocked function returning simulated TXN IDs | PCI-DSS certified gateway (Razorpay / Stripe) |
| **Fulfillment / Delivery** | Mocked status transitions in SQLite | 3PL Carrier Webhooks & WMS integration |
| **Channels** | Simulated via `channel` metadata tag | Native WhatsApp Cloud API, Webhooks, Push, POS |
| **RAG / Knowledge Retrieval** | In-Memory TF-IDF cosine similarity | Dense Neural Embeddings + pgvector / FAISS / Qdrant |
| **Recommendations** | TF-IDF + Order Co-occurrence pass | Two-Tower Neural Embeddings + Clickstream Feature Store |
| **Persistence** | SQLite (`aura.db`) | PostgreSQL + Redis session store |
| **Security / Auth** | Simulated user IDs | OAuth2, JWT, Encrypted customer PII |
| **Evaluation** | Streamlit + Ground-truth benchmark suite | Continuous CI/CD evaluation + Live A/B testing |
