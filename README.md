# Project P1 - Document RAG System

Project P1 is a strict, document-faithful internal assistant designed to help users find information that explicitly exists in approved documents.

P1 is a **production-intended, enterprise-grade RAG system** designed around one core principle:

> **Correctness over coverage.**

If an answer is **not explicitly present in the documents**, P1 will **refuse** rather than guess.

P1 is **not a chatbot**.  
P1 is a **document-faithful knowledge interface**.

---

## What P1 Does

At a high level, P1:
- Accepts user questions
- Searches only the tenant’s uploaded documents
- Answers **only when the documents explicitly contain the answer**
- Otherwise returns a **controlled refusal or guided fallback**

No hallucination. No inference. No synthesis.

---

## Core Behavior (Non-Negotiable)

P1 enforces these guarantees at the API level:

- Answers are returned **only if present in documents**
- No hallucination
- No inference
- No cross-document synthesis
- Exactly **one response mode per request**

### Response Modes

- **direct_answer**  
  Returned when the document explicitly answers the question.

- **guided_fallback**  
  Returned when related content exists, but no direct answer is stated.  
  Provides extractive highlights only — not an answer.

- **hard_refusal**  
  Returned when the documents do not support the question.  
  Refusal is a **success state**, not an error.

---

## Tenant Model

P1 is **tenant-aware by design**.

data/
└── tenants/
└── <tenant_id>/
├── docs/
└── chroma/



- Each tenant has isolated documents
- Each tenant has its own vector store
- No global retrieval
- No cross-tenant leakage


---

## Document Lifecycle (Important)

P1 intentionally separates **uploading** from **indexing**.

### 1. Upload
Documents are uploaded and stored, but **not indexed automatically**.

Why?
- Prevents accidental re-indexing
- Keeps indexing explicit and auditable
- Allows future background or batch indexing

### 2. Index
Indexing is triggered explicitly by the user.

Only indexed documents are searchable.

### 3. Query
Queries operate **only on indexed documents** for that tenant.

If no documents are indexed:
- P1 returns a **hard_refusal** explaining that no documents are available.

---

## API Overview (Current)

### Query

POST /query

Requires:
- tenant_id
- conversation_id
- query

Returns one of:
- direct_answer
- guided_fallback
- hard_refusal

---

### Document Management (v1.4)

POST /tenants/{tenant_id}/documents
POST /tenants/{tenant_id}/documents/index
GET /tenants/{tenant_id}/documents
DELETE /tenants/{tenant_id}/documents/{filename}


Upload ≠ Index (by design).

---

## CLI (Developer Tool Only)

P1 includes a thin CLI for development and testing.

- Raw JSON passthrough
- No logic
- No retries
- No interpretation

The CLI is **not** a product UI.

---

## What Is Implemented So Far (v1.4)

- Document-faithful query engine (frozen)
- Deterministic refusal behavior
- Tenant-aware retrieval
- Explicit document ingestion & indexing
- Per-tenant document management
- CI-safe refusal-only testing

---

## What Is Intentionally Not Implemented Yet

These are **planned**, not missing:

- Authentication / authorization
- Persistence of conversations & messages
- Metrics & observability
- UI
- Background ingestion workers
- Auto-index on upload

Each will be added **without changing core semantics**.

---

## Philosophy to Preserve

P1 is not trying to be:
- Helpful at all costs
- A search engine
- A summarizer

P1 is:
- Refusal-first
- Enterprise-safe
- Document-faithful by construction

---

## Versioning

- Current release: **v1.4**
- Core decision engine is **frozen**
- All future work wraps around the core

---

## Next Planned Releases (High-Level)

- v1.5: Authentication & tenant binding
- v1.6: Persistence (conversations, messages)
- v1.7: Observability (metrics, logs)
- v1.8+: UI (strict API consumer)

---

If you’re reading this README and thinking  
“this system refuses a lot” — that’s the point.
