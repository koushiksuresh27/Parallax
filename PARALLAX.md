# PARALLAX

## Product Requirements Document

**Version:** 2.0 — Student Portfolio Edition | AI Engineer Intern

## 1. Product Overview

Parallax is an AI-powered operational intelligence platform that helps analysts investigate business problems by connecting structured datasets with unstructured documents. Instead of simply retrieving documents or answering questions from individual files, it retrieves relevant information, identifies relationships between records, analyses the evidence and generates explanations supported by traceable sources.

**Core idea:** Ask a business question, investigate the underlying data, receive an evidence-backed explanation.

### Why This Project Stands Out on a Resume

Parallax is designed to demonstrate the exact skills AI Engineer intern roles look for. Every technology choice is deliberate and explainable.

| Skill Signal | How Parallax Shows It |
| --- | --- |
| **LangGraph** | Multi-node stateful investigation workflow with conditional routing and retry logic |
| **LangChain** | RAG chains, prompt templates, embeddings, SQL retrieval chain |
| **RAG** | Hybrid retrieval across Qdrant (semantic) and PostgreSQL (structured) |
| **Redis** | Embedding cache, query cache, LangGraph state persistence |
| **Docker** | Full multi-service Compose stack with five services |
| **System design** | Evidence-first architecture, provenance tracking, no hallucinated results |
| **Python / FastAPI** | Production-style REST API backend with async endpoints |
| **Real data** | Olist Brazilian E-Commerce public dataset (100K+ orders) |

### The Core Example

An analyst uploads the Olist e-commerce dataset containing orders, customers, sellers, products and delivery information and asks:

> *"Why are deliveries getting delayed?"*

Parallax should be able to:

1. Identify orders where the actual delivery timestamp exceeds the estimated delivery timestamp.
2. Retrieve relevant order and delivery records via SQL.
3. Group by seller state, product category and customer region to find patterns.
4. Retrieve any uploaded documents related to logistics or fulfilment via semantic search.
5. Generate a cited explanation distinguishing correlation from causation.
6. Present every finding with a reference to the underlying record or document chunk.

The system must always distinguish between verified facts, observed patterns and possible explanations.

## 2. Core Product Capabilities

### 2.1 Data and Document Ingestion

Users upload structured and unstructured information through the admin interface.

**Supported formats:** CSV, XLSX, PDF, DOCX, TXT, JSON

The system validates uploaded files, stores originals, extracts their contents, preserves metadata, tracks ingestion status, detects duplicates and allows failed jobs to be retried.

### 2.2 Structured Data Processing

The primary demonstration dataset is the **Olist Brazilian E-Commerce public dataset** (Kaggle, openly licensed).

The system imports CSVs into PostgreSQL, infers column types, preserves original record identifiers and connects related records using actual foreign keys. All calculations — delivery delay, order counts, freight costs — are performed using Python and SQL exclusively. The LLM never performs arithmetic.

> **Resume talking point:** "All numerical results are deterministic — computed in SQL, not by an LLM. This prevents hallucination of statistics."

### 2.3 Document Processing

Documents are extracted using **Docling**, chunked using LangChain's `RecursiveCharacterTextSplitter`, embedded and stored in Qdrant. Source metadata (filename, page number, chunk index) is preserved at every step so every retrieved passage can be traced back to its origin.

### 2.4 RAG — Evidence Retrieval (Hybrid)

This is the core RAG implementation and must be explained clearly in any interview.

**Two-channel hybrid retrieval:**

**Channel 1 — Semantic retrieval (Qdrant + LangChain)**

- Document chunks are embedded using `OpenAIEmbeddings` or `HuggingFaceEmbeddings`.
- The investigation question is embedded and used to query Qdrant via `QdrantVectorStore.as_retriever()`.
- The top-k most semantically relevant passages are returned with their source metadata.

**Channel 2 — Structured retrieval (PostgreSQL + LangChain SQL chain)**

- LangChain's `create_sql_query_chain` translates the investigation question into a parameterised SQL query.
- The query runs against the Olist tables via SQLAlchemy.
- Returned records carry their original identifiers (e.g. `order_id`, `seller_id`).

**Evidence fusion** Results from both channels are merged into a unified evidence bundle — a structured list of records and document passages — that is passed as context to the LLM analysis node. The LLM never sees the raw database; it only sees retrieved, labelled evidence.

> **Resume talking point:** "Hybrid RAG combining vector and relational retrieval is a real production pattern. Most tutorial RAG projects only implement vector search. This shows I understand when each approach is appropriate."

## 3. LangGraph Investigation Workflow

This is the centrepiece of the technical demonstration and the most important part to understand and explain.

### Why LangGraph, Not a Simple Chain?

A LangChain chain runs linearly. The investigation workflow needs:

- **State that persists** across multiple async steps.
- **Conditional routing** (e.g. retry analysis if verification fails; skip to report if no records found).
- **Observable progress** so the frontend can show which node is running.
- **Resumability** if a step fails mid-investigation.

LangGraph provides all of this through a typed `StateGraph` with named nodes and explicit edges.

> **Interview answer:** "I chose LangGraph because the investigation is not a linear pipeline. It has conditional branches — if structured retrieval returns nothing, the workflow routes directly to report generation with a limitation note rather than trying to analyse empty evidence. A simple chain cannot express this."

### Investigation State

```python
from typing import TypedDict, Annotated
import operator

class InvestigationState(TypedDict):
    question: str                    # Original analyst question
    plan: list[str]                  # Sub-queries from planning node
    structured_evidence: list[dict]  # Records from PostgreSQL
    document_evidence: list[dict]    # Chunks from Qdrant
    patterns: list[str]              # Identified patterns
    explanations: list[str]          # LLM-generated explanations
    confidence: str                  # "high" | "medium" | "low"
    citations: list[dict]            # Source references
    limitations: list[str]           # What was missing
    final_report: str                # Assembled investigation report
    retry_count: int                 # Tracks verification retries
```

### Workflow Nodes

| Node | Type | Responsibility |
| --- | --- | --- |
| `plan_investigation` | LLM | Decomposes the question into structured + document sub-queries |
| `retrieve_structured` | Deterministic | SQL queries via LangChain SQL chain against PostgreSQL |
| `retrieve_documents` | Deterministic | Qdrant semantic search with Redis cache check |
| `analyse_evidence` | LLM | Analyses the fused evidence bundle, identifies patterns |
| `verify_findings` | LLM | Cross-checks conclusions against the retrieved evidence |
| `generate_report` | LLM | Assembles the final cited investigation report |

### Conditional Routing (Edges)

```python
def route_after_retrieval(state: InvestigationState) -> str:
    if not state["structured_evidence"] and not state["document_evidence"]:
        return "generate_report"  # Skip analysis — nothing to work with
    return "analyse_evidence"

def route_after_verification(state: InvestigationState) -> str:
    if state["confidence"] == "low" and state["retry_count"] < 1:
        return "analyse_evidence"  # One retry
    return "generate_report"

workflow.add_conditional_edges("retrieve_documents", route_after_retrieval)
workflow.add_conditional_edges("verify_findings", route_after_verification)
```

### State Persistence with Redis

Longrunning investigations are checkpointed to Redis using LangGraph's built-in checkpointer interface. This means:

- An in-progress investigation survives a backend restart.
- The frontend can poll for the current node state.
- Investigations can be resumed from any node.

```python
from langgraph.checkpoint.redis import AsyncRedisSaver

checkpointer = AsyncRedisSaver.from_conn_string(settings.REDIS_URL)
app = workflow.compile(checkpointer=checkpointer)
```

### Full Workflow Graph

```
[START]
   │
   ▼
plan_investigation
   │
   ▼
retrieve_structured ──────────────────────┐
   │                                      │
   ▼                                      │
retrieve_documents                        │
   │                                      │
   ├─ no evidence found ─────────────────▼
   │                              generate_report
   ▼                                      ▲
analyse_evidence                          │
   │                                      │
   ▼                                      │
verify_findings                           │
   │                                      │
   ├─ low confidence + retry < 1 ─► analyse_evidence
   │
   └─ otherwise ─────────────────────────┘

[END]
```

## 4. LangChain Integration Points

LangChain is used in targeted, explainable ways — not as a catch-all abstraction.

| Use Case | LangChain Component |
| --- | --- |
| LLM calls with prompt templates | `ChatPromptTemplate`, `ChatOpenAI` |
| SQL query generation from natural language | `create_sql_query_chain` |
| Document chunking | `RecursiveCharacterTextSplitter` |
| Embedding generation | `OpenAIEmbeddings` or `HuggingFaceEmbeddings` |
| Qdrant vector retriever | `QdrantVectorStore.as_retriever()` |
| Structured output parsing | `PydanticOutputParser` |

> **Interview answer to "Why LangChain?":** "I use specific LangChain components where they add clear value — the SQL chain, the Qdrant retriever and prompt templates. I don't use it as a catch-all. Where a component would just add indirection, I call the library directly."

### Sample Prompt Template (Planning Node)

```python
plan_prompt = ChatPromptTemplate.from_messages([
    ("system", """
    You are an operational analyst. Given a business question,
    decompose it into:
    1. A list of SQL sub-queries to run against the database.
    2. A semantic search query for retrieving relevant documents.
    Return a JSON object with keys 'sql_queries' and 'doc_query'.
    Available tables: {table_names}
    """),
    ("human", "{question}")
])
```

---

## 5. Redis Usage — Specific and Defensible

Redis serves three concrete purposes. You must be able to explain each one.

### Purpose 1 — Embedding Cache

Embedding API calls are expensive. When the same document chunk appears in multiple investigations, its embedding should not be recomputed.

```python
async def get_or_compute_embedding(text: str) -> list[float]:
    cache_key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
    embedding = await embeddings.aembed_query(text)
    await redis.set(cache_key, json.dumps(embedding), ex=86400)  # 24h TTL
    return embedding
```

### Purpose 2 — Query Result Cache

Identical SQL sub-queries within a session return the same records. Caching avoids redundant database round-trips during the analysis and retry phases.

```python
cache_key = f"query:{hashlib.md5(sql.encode()).hexdigest()}"
TTL = 600  # 10 minutes
```

### Purpose 3 — LangGraph State Persistence

LangGraph checkpoints investigation state to Redis at every node transition. If the FastAPI backend restarts mid-investigation, the workflow can resume from the last completed node rather than starting over.

> **Interview answer to "Why Redis?":** "Redis serves three distinct purposes — embedding cache to reduce API costs, SQL result cache to avoid redundant queries within a session, and LangGraph state checkpointing for investigation resumability. I can remove any one of them and explain exactly what degrades."

## 6. Technical Architecture

### Full Stack

```
Frontend:   React + TypeScript + Vite
Backend:    Python 3.11 + FastAPI + SQLAlchemy 2 + Alembic
Database:   PostgreSQL 15 (source of truth)
Vector DB:  Qdrant (document semantic retrieval)
Cache:      Redis 7 (embedding cache, query cache, LangGraph checkpoints)
AI:         LangChain + LangGraph + OpenAI API
Docs:       Docling (PDF/DOCX extraction + OCR)
Deploy:     Docker + Docker Compose
```

### Repository Structure

```
parallax/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers (sources, investigations)
│   │   ├── core/             # Config, DB session, Redis client
│   │   ├── ingestion/        # Upload, CSV import, doc processing pipeline
│   │   ├── retrieval/        # Qdrant retriever, SQL retriever, fusion
│   │   ├── investigation/    # LangGraph workflow, nodes, state definition
│   │   ├── models/           # SQLAlchemy ORM models
│   │   └── schemas/          # Pydantic request/response schemas
│   ├── migrations/           # Alembic migration files
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── pages/            # Dashboard, Sources, Workspace, History
│   │   ├── components/       # EvidencePanel, NodeProgress, CitationCard
│   │   └── api/              # Typed API client
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

### Core Database Schema

```sql
-- Source tracking
data_sources (
  id UUID PRIMARY KEY,
  name TEXT,
  file_type TEXT,
  file_path TEXT,
  status TEXT,          -- pending | processing | ready | failed
  uploaded_at TIMESTAMPTZ
);

-- Olist structured tables (imported as-is from CSV)
olist_orders (order_id, customer_id, status, purchase_ts,
              approved_ts, delivered_ts, estimated_delivery_ts);
olist_order_items (order_id, product_id, seller_id, price, freight_value);
olist_customers (customer_id, zip_code_prefix, city, state);
olist_sellers (seller_id, zip_code_prefix, city, state);
olist_products (product_id, category_name, weight_g);
olist_reviews (review_id, order_id, score, comment_message);

-- Document processing
document_chunks (
  id UUID PRIMARY KEY,
  source_id UUID REFERENCES data_sources(id),
  content TEXT,
  page_number INT,
  chunk_index INT,
  qdrant_point_id UUID
);

-- Investigation history
investigations (
  id UUID PRIMARY KEY,
  question TEXT,
  status TEXT,
  created_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

investigation_evidence (
  id UUID PRIMARY KEY,
  investigation_id UUID REFERENCES investigations(id),
  source_type TEXT,     -- "structured" | "document"
  record_id TEXT,       -- e.g. order_id value
  content TEXT,
  relevance_score FLOAT
);

investigation_findings (
  id UUID PRIMARY KEY,
  investigation_id UUID REFERENCES investigations(id),
  finding_type TEXT,    -- "fact" | "pattern" | "explanation"
  content TEXT,
  confidence TEXT,
  evidence_ids UUID[]
);
```

### Docker Compose Stack

```yaml
# docker-compose.yml
services:

  api:
    build: ./backend
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db, qdrant, redis]

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: parallax
      POSTGRES_USER: parallax
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes: ["postgres_data:/var/lib/postgresql/data"]

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes: ["qdrant_data:/qdrant/storage"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [api]

volumes:
  postgres_data:
  qdrant_data:
```

> **Interview answer to "Walk me through your Docker setup":** "Five services — FastAPI, PostgreSQL, Qdrant, Redis and the React frontend served by nginx. All secrets are environment variables in a `.env` file never committed to source control. I can bring the entire stack up with `docker compose up` and tear it down cleanly."

## 7. Application Interfaces

The frontend is React + TypeScript + Vite with four screens.

### A. Dashboard

- Uploaded dataset count and document count.
- Recent investigations with status badges.
- Key Olist metrics once data is ingested (order count, average delay).

### B. Data Sources

- File upload with drag-and-drop.
- Processing status per source (pending / processing / ready / failed).
- Retry button for failed sources.
- Source metadata (row count, columns, page count).

### C. Investigation Workspace

- Natural-language question input field.
- **LangGraph node progress bar** — shows which node is currently running.
- Retrieved records panel (structured evidence with IDs).
- Retrieved document passages panel (with page and chunk references).
- Final investigation report with inline citation chips.
- Each citation chip opens the source record or document chunk.

### D. Investigation History

- Paginated list of past investigations.
- Question and completion timestamp.
- Link to full report and evidence for each.

> The interface prioritises investigation results and evidence. It does not display unnecessary charts or technical metrics.

---

## 8. Development Phases (9-Week Plan)

### Phase 0 — Architecture and Setup (Week 1)

- Finalise this PRD.
- Set up repo with linting, pre-commit hooks, `pyproject.toml`.
- Write the full database schema.
- Spin up Docker Compose stack locally (Postgres, Qdrant, Redis).
- Confirm Olist dataset is downloaded and importable.

### Phase 1 — Backend Foundation (Week 2)

- FastAPI skeleton with lifespan events.
- PostgreSQL connection via SQLAlchemy 2 async.
- All Alembic migrations for the full schema.
- `GET /health` endpoint verifying Postgres, Redis and Qdrant connectivity.
- `.env.example` with all required variables.

### Phase 2 — Data Ingestion (Week 3)

- File upload endpoint (`POST /sources`).
- File type and size validation.
- Background task for CSV import into Olist tables.
- Source status tracking.
- Duplicate detection via file hash.
- `GET /sources` and `GET /sources/{id}` endpoints.

### Phase 3 — Document Processing (Week 4)

- Docling integration for PDF and DOCX extraction.
- Chunking pipeline with LangChain `RecursiveCharacterTextSplitter`.
- Embedding generation with Redis cache.
- Qdrant upsert with source metadata.
- Document chunk provenance stored in `document_chunks` table.

### Phase 4 — Retrieval (Week 5)

- `QdrantVectorStore.as_retriever()` integration.
- LangChain `create_sql_query_chain` against Olist tables.
- Redis query result cache for structured retrieval.
- Evidence fusion function merging both channels.
- Unit tests for retrieval with Olist test data.

### Phase 5 — LangGraph Investigation Workflow (Weeks 6–7)

- Define `InvestigationState` TypedDict.
- Implement all six workflow nodes.
- Wire conditional edges (empty evidence → report; low confidence → retry).
- Redis checkpointer for state persistence.
- Persist investigation and evidence to PostgreSQL on completion.
- End-to-end test: "Why are deliveries delayed?" against Olist data.

### Phase 6 — Frontend (Week 8)

- Vite + React + TypeScript scaffold.
- All four screens with routing.
- Investigation Workspace with node progress display.
- Evidence panel with citation chips.
- API client using typed fetch.

### Phase 7 — Integration and Polish (Week 9)

- Full `docker compose up` integration test.
- End-to-end test suite covering the full demonstration flow.
- README with architecture diagram, setup instructions and demo GIF.
- Record a 2-minute demo video for portfolio.
- Evaluate against five representative questions and document results.

## 9. Resume and Interview Guidance

### One-Liner for Resume / LinkedIn / Cover Letters

> \*"An AI-powered operational intelligence platform using a LangGraph stateful investigation workflow with hybrid RAG (Qdrant + PostgreSQL), LangChain orchestration, Redis caching and a full Docker Compose deployment."

### Resume Bullet Points

Use these in your Projects section:

- Built a **LangGraph** stateful investigation workflow with six nodes, conditional routing and Redis checkpointing for investigation resumability.
- Implemented **hybrid RAG** combining Qdrant semantic search and LangChain SQL retrieval against PostgreSQL, with evidence fusion before LLM analysis.
- Engineered an evidence-first architecture ensuring all LLM outputs are grounded in retrieved records with full citation provenance — no hallucinated statistics.
- Containerised the full stack (FastAPI, PostgreSQL, Qdrant, Redis, React) using **Docker Compose** with a single-command setup.
- Processed the Olist Brazilian E-Commerce dataset (100K+ orders) for investigation using natural-language questions.
- Used **Redis** for three distinct purposes: embedding cost reduction, SQL query caching and LangGraph state persistence.

### Five Questions You Must Be Able to Answer

**Q1: Why LangGraph instead of a simple LangChain chain?**

> "The investigation has conditional paths that a linear chain cannot express. If structured retrieval returns no records, the workflow skips analysis and routes directly to report generation with a limitation note. If the verification node judges the conclusion low-confidence, it retries the analysis node once. LangGraph also persists state via Redis, so long-running investigations survive a backend restart. None of this is possible with a plain chain."

**Q2: Why Redis? What breaks without it?**

> "Redis serves three purposes. Without the embedding cache, every investigation re-embeds the same document chunks and pays the API cost again. Without the query cache, identical SQL sub-queries hit the database on every analysis and retry step. Without LangGraph checkpointing, an in-progress investigation is lost if the backend restarts. Each removal has a concrete, explainable consequence."

**Q3: How does your RAG pipeline actually work?**

> "Hybrid retrieval across two channels. Document questions go to Qdrant via LangChain's retriever using semantic similarity. Structured questions go through LangChain's SQL chain, which translates the sub-query into parameterised SQL against the Olist PostgreSQL tables. Results from both are merged into a single evidence bundle — a labelled list of records and passages — which is the only thing the LLM analysis node sees. It never touches the database directly."

**Q4: How do you prevent LLM hallucination?**

> "Three controls. First, the LLM only receives retrieved evidence as context — it cannot invent records it hasn't been given. Second, all numerical calculations — delivery delays, order counts, averages — are computed in SQL and passed as facts, not asked of the LLM. Third, the verify node cross-checks the generated explanation against the evidence bundle and flags low-confidence conclusions, triggering a retry."

**Q5: Walk me through your Docker Compose setup.**

> "Five services: `api` running FastAPI, `db` running PostgreSQL 15, `qdrant`, `redis` and `frontend` serving the React build via nginx. All credentials are environment variables from a `.env` file never committed to source control. `docker compose up` starts the full stack. Volumes persist Postgres and Qdrant data across restarts."

---

## 10. Architecture Principles

1. **Simplicity first:** Implement the smallest solution that fulfils the requirement.
2. **One source of truth:** PostgreSQL is the canonical database.
3. **Evidence before explanation:** The LLM works with retrieved evidence only.
4. **Deterministic computation:** Python and SQL for all calculations.
5. **Traceability:** Findings link back to their sources.
6. **No silent fallbacks:** Failed integrations must be reported clearly.
7. **No unnecessary abstractions:** No generic frameworks for a single use case.
8. **Incremental development:** Each feature tested before the next is introduced.

---

## 11. What Is Explicitly Out of Scope

These are excluded deliberately so the project remains coherent and you can explain every part.

- Neo4j or a separate graph database.
- Kubernetes.
- Microservices architecture.
- Multiple LLM providers.
- Multiple autonomous AI agents.
- Enterprise multi-tenancy or billing.
- Predictive ML models without a demonstrated use case.
- Autonomous actions that modify business records.

---

## 12. Success Criteria

Parallax will be considered ready for portfolio when an analyst can:

1. Upload the Olist CSV dataset and have it ingested into PostgreSQL.
2. Upload at least one supporting PDF document.
3. Ask: *"Why are some orders taking longer to reach customers?"*
4. Watch the LangGraph workflow progress through its six nodes.
5. Receive a report with specific order IDs, seller regions and delivery statistics cited.
6. Click any citation and trace it back to the source record or document chunk.
7. Re-run the investigation without corrupting existing data.
8. Answer all five interview questions above from memory.
