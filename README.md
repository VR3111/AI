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

## Authentication (Required)

All API endpoints (except `/health`) require authentication.

P1 uses **Bearer JWT authentication**.

- Requests **must** include an `Authorization` header:

Authorization: Bearer <JWT>


- JWTs must include a `tenant_id` claim
- Tokens are **verified**, not generated, by P1
- Missing or invalid tokens result in **401**
- Tenant mismatches result in **403**

The tenant context is derived **exclusively from the token**.

Request payloads or parameters **cannot override** the authenticated tenant.

---

## Tenant Model

P1 is **tenant-aware by design**.

data/
└── tenants/
└── <tenant_id>/
├── docs/
├── chroma/
└── p1.db


- Each tenant has isolated documents
- Each tenant has its own vector store
- Each tenant has its own persistence database
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
- Authorization header (Bearer JWT)
- conversation_id
- query

Returns exactly one of:
- direct_answer
- guided_fallback
- hard_refusal

---

### Read APIs (UI-Critical)

GET /conversations
GET /conversations/{conversation_id}


- Returns persisted conversation history
- Tenant-scoped
- Read-only
- Authentication required

---

### Document Management

POST /tenants/{tenant_id}/documents
POST /tenants/{tenant_id}/documents/index
GET /tenants/{tenant_id}/documents
DELETE /tenants/{tenant_id}/documents/{filename}


- Tenant in the path **must match** the tenant in the JWT
- Upload ≠ Index (by design)

---

## Persistence (Implemented)

P1 persists all query interactions.

- Per-tenant SQLite database
- Conversations and queries stored
- Restart-safe
- Multi-worker safe
- No in-memory conversation state

Persistence is **best-effort** and **never blocks query execution**.

---

## CLI (Developer Tool Only)

P1 includes a thin CLI for development and testing.

- Raw JSON passthrough
- No logic
- No retries
- No interpretation
- Requires `P1_AUTH_TOKEN` to be set

The CLI is **not** a product UI.

---

## What Is Implemented (Backend Core Complete)

- Document-faithful query engine (frozen)
- Deterministic refusal behavior
- Tenant-aware retrieval
- Explicit document ingestion & indexing
- Per-tenant persistence (conversations & queries)
- Read APIs for UI consumption
- JWT-based authentication & tenant binding
- CI-safe refusal-only testing

---

## What Is Intentionally Not Implemented Yet

These are **planned**, not missing:

- Metrics & observability
- UI
- Background ingestion workers
- Auto-index on upload
- Role-based access control (RBAC)

All future features will wrap around the core without changing semantics.

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

- Current release tag: **p1-v1-backend-core-complete**
- Backend core is **frozen**
- All future backend changes are v2+

---

## Next Planned Work (High-Level)

- UI (strict API consumer)
- Observability
- Controlled production rollout

---

If you’re reading this README and thinking  
“this system refuses a lot” —> THATS THE POINT!!!!!


