import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI
from fastapi import Request
from pydantic import BaseModel

from app.llm import generate_answer
from app.retrieve import retrieve, dedupe_results, MAX_DISTANCE

# -----------------------------------------------------
# App + CI mode
# -----------------------------------------------------
CI_MODE = os.getenv("CI") == "true"

app = FastAPI(title="Internal Assistant API")

from app.auth import auth_middleware
auth_middleware(app)

# -----------------------------------------------------
# Health (always available)
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
# Helpers: contract wrapper
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
# Request / State
# =====================================================
conversation_store = {}

class QueryRequest(BaseModel):
    query: str
    conversation_id: str
    tenant_id: Optional[str] = None
    debug: bool = False

# =====================================================
# Query classification helpers
# =====================================================
def is_definition_query(query: str) -> bool:
    return bool(re.match(r"^\s*what\b.*\b(are|is|means|refers to)\b", query, re.I))


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
    return query.strip().lower() in {"tell me more", "explain more", "more details", "continue", "go on"}


def is_reset_query(query: str) -> bool:
    return query.strip().lower() in {"new topic", "reset", "clear context", "start over"}

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

    if is_reset_query(original_query):
        conversation_store.pop((tenant_id, conversation_id), None)
        return wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="hard_refusal",
            answer=refusal_message("reset"),
            citations=[],
            artifacts={"reason": "reset"},
            debug=None,
        )

    state = conversation_store.setdefault((tenant_id, conversation_id), {"last_successful_query": None})

    rewritten_query = (
        f"In the context of {state['last_successful_query']}, {original_query}"
        if len(original_query.split()) <= 6 and state["last_successful_query"]
        else original_query
    )

    if is_vague_query(original_query):
        return wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="hard_refusal",
            answer=refusal_message("no_chunks"),
            citations=[],
            artifacts={"reason": "vague_query"},
            debug=None,
        )

    if mentions_external_entity(original_query):
        return wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="hard_refusal",
            answer=refusal_message("external_entity"),
            citations=[],
            artifacts={"reason": "external_entity"},
            debug=None,
        )

    raw_results, status = retrieve(rewritten_query, k=6, tenant_id=tenant_id, return_status=True)
    results = dedupe_results(raw_results)

    if status == "no_documents_ingested":
        return wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="hard_refusal",
            answer="There are no documents available yet to answer this question.",
            citations=[],
            artifacts={"reason": "no_documents_ingested"},
            debug=None,
        )

    if not results:
        return wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="hard_refusal",
            answer=refusal_message("no_chunks"),
            citations=[],
            artifacts={"reason": "no_chunks"},
            debug=None,
        )

    best_score = min(score for _, score in results)
    if is_explanatory_query(original_query) or best_score > MAX_DISTANCE:
        return wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="guided_fallback",
            answer="",
            citations=[],
            artifacts={"reason": "No direct answer was found in the documents for this question."},
            debug=None,
        )

    answer = generate_answer(rewritten_query, results)
    state["last_successful_query"] = original_query

    return wrap_response(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        query=original_query,
        mode="direct_answer",
        answer=answer,
        citations=[],
        artifacts={"additional_resources": []},
        debug=None,
    )
