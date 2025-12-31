import os
import re
import uuid
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.llm import generate_answer
from app.retrieve import retrieve, dedupe_results, MAX_DISTANCE
from app.persist import save_query_result
from app.read_api import router as read_router

# -----------------------------------------------------
# App + CI mode
# -----------------------------------------------------
CI_MODE = os.getenv("CI") == "true"

app = FastAPI(title="Internal Assistant API")
app.include_router(read_router)

from app.auth import auth_middleware
auth_middleware(app)

# -----------------------------------------------------
# Health
# -----------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

# -----------------------------------------------------
# Ingestion API (DISABLED IN CI)
# -----------------------------------------------------
if not CI_MODE:
    from app.ingest_api import router as ingest_router
    app.include_router(ingest_router)

# =====================================================
# Helpers
# =====================================================
def now_iso():
    return datetime.now(timezone.utc).isoformat()


def wrap_response(
    *,
    tenant_id: str,
    conversation_id: str,
    query: str,
    mode: str,
    answer: str,
    citations: list,
    artifacts: dict,
    debug: dict | None,
):
    return {
        "request_id": str(uuid.uuid4()),
        "created_at": now_iso(),
        "tenant_id": tenant_id,
        "conversation_id": conversation_id,
        "query": query,
        "mode": mode,
        "answer": answer,
        "citations": citations,
        "artifacts": artifacts,
        "debug": debug,
    }


# =====================================================
# Persistence wrapper (BEST-EFFORT)
# =====================================================
def persist_and_return(response: dict):
    try:
        save_query_result(
            tenant_id=response["tenant_id"],
            conversation_id=response["conversation_id"],
            payload=response,
        )
    except Exception:
        pass
    return response


# =====================================================
# DB-backed conversation state
# =====================================================
def get_last_successful_query(tenant_id: str, conversation_id: str) -> Optional[str]:
    db_path = os.path.join("data", "tenants", tenant_id, "p1.db")
    if not os.path.isfile(db_path):
        return None

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT query
            FROM queries
            WHERE tenant_id = ?
              AND conversation_id = ?
              AND mode = 'direct_answer'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (tenant_id, conversation_id),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# =====================================================
# Request model
# =====================================================
class QueryRequest(BaseModel):
    query: str
    conversation_id: str
    tenant_id: Optional[str] = None
    debug: bool = False


# =====================================================
# Query classification helpers
# =====================================================
def is_explanatory_query(query: str) -> bool:
    return bool(re.match(r"^\s*(how|why|in what way|in which way)\b", query, re.I))


def mentions_external_entity(query: str) -> bool:
    comparison_keywords = {"better", "worse", "than", "vs", "versus", "compare"}
    words = set(re.findall(r"\b\w+\b", query.lower()))
    if not words.intersection(comparison_keywords):
        return False
    entities = re.findall(r"\b[A-Z][a-zA-Z]+\b", query)
    return len(entities) >= 2


def is_vague_query(query: str) -> bool:
    return query.strip().lower() in {
        "tell me more", "explain more", "more details", "continue", "go on"
    }


def is_reset_query(query: str) -> bool:
    return query.strip().lower() in {
        "new topic", "reset", "clear context", "start over"
    }


# =====================================================
# Refusal UX
# =====================================================
def refusal_message(reason: str) -> str:
    if reason == "no_chunks":
        return "Please provide more context so I can answer accurately."
    if reason == "reset":
        return "Context has been reset. Please ask a new question."
    return "The documents do not answer this question."


# =====================================================
# Main Query Endpoint
# =====================================================
@app.post("/query")
def query_docs(payload: QueryRequest, request: Request):
    original_query = payload.query
    tenant_id = request.state.tenant_id
    conversation_id = payload.conversation_id

    # ---------------- reset ----------------
    if is_reset_query(original_query):
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer=refusal_message("reset"),
                citations=[],
                artifacts={"reason": "reset"},
                debug=None,
            )
        )

    # ---------------- rewrite (DB-backed) ----------------
    last_successful_query = get_last_successful_query(tenant_id, conversation_id)

    rewritten_query = (
        f"In the context of {last_successful_query}, {original_query}"
        if len(original_query.split()) <= 6 and last_successful_query
        else original_query
    )

    # ---------------- refusals ----------------
    if is_vague_query(original_query):
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer=refusal_message("no_chunks"),
                citations=[],
                artifacts={"reason": "vague_query"},
                debug=None,
            )
        )

    if mentions_external_entity(original_query):
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer=refusal_message("external_entity"),
                citations=[],
                artifacts={"reason": "external_entity"},
                debug=None,
            )
        )

    # ---------------- retrieval ----------------
    raw_results, status = retrieve(
        rewritten_query, k=6, tenant_id=tenant_id, return_status=True
    )
    results = dedupe_results(raw_results)

    if status == "no_documents_ingested":
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer="There are no documents available yet to answer this question.",
                citations=[],
                artifacts={"reason": "no_documents_ingested"},
                debug=None,
            )
        )

    if not results:
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer=refusal_message("no_chunks"),
                citations=[],
                artifacts={"reason": "no_chunks"},
                debug=None,
            )
        )

    best_score = min(score for _, score in results)
    if is_explanatory_query(original_query) or best_score > MAX_DISTANCE:
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="guided_fallback",
                answer="",
                citations=[],
                artifacts={"reason": "No direct answer was found in the documents for this question."},
                debug=None,
            )
        )

    # ---------------- direct answer ----------------
    contexts = [
    {
        "content": doc.page_content,
        "source": doc.metadata.get("source"),
        "page": doc.metadata.get("page"),
    }
    for doc, _score in results
    ]

    answer = generate_answer(rewritten_query, contexts)

    return persist_and_return(
        wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="direct_answer",
            answer=answer,
            citations=[],
            artifacts={"additional_resources": []},
            debug=None,
        )
    )
