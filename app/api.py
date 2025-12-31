from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional
import re
import uuid

from datetime import datetime, timezone

from app.llm import generate_answer
from app.retrieve import retrieve, dedupe_results, MAX_DISTANCE

from app.ingest_api import router as ingest_router


app = FastAPI(title="Internal Assistant API")

# Mount ingestion API (tenant-aware document upload & indexing)
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
# Citation helpers
# =====================================================

def dedupe_citations(relevant_chunks):
    seen = set()
    unique = []
    for r in relevant_chunks:
        key = (r["source"], r["page"])
        if key in seen:
            continue
        seen.add(key)
        unique.append({
            "source_id": None,
            "source_name": r["source"],
            "page": r["page"],
            "chunk_id": None,
            "quote": None,
            "doc_hash": None,
        })
    return unique


def citations_from_bullets(bullets):
    seen = set()
    out = []
    for b in bullets:
        key = (b["source"], b["page"])
        if key not in seen:
            seen.add(key)
            out.append({
                "source_id": None,
                "source_name": b["source"],
                "page": b["page"],
                "chunk_id": None,
                "quote": None,
                "doc_hash": None,
            })
    return out


# =====================================================
# Query classification helpers
# =====================================================

def is_definition_query(query: str) -> bool:
    return bool(
        re.match(
            r"^\s*what\b.*\b(are|is|means|refers to)\b",
            query.strip(),
            flags=re.IGNORECASE,
        )
    )


def is_explanatory_query(query: str) -> bool:
    return bool(
        re.match(
            r"^\s*(how|why|in what way|in which way)\b",
            query.strip(),
            flags=re.IGNORECASE,
        )
    )


def mentions_external_entity(query: str) -> bool:
    comparison_keywords = {"better", "worse", "than", "vs", "versus", "compare"}
    words = set(re.findall(r"\b\w+\b", query.lower()))
    if not words.intersection(comparison_keywords):
        return False

    entities = re.findall(r"\b[A-Z][a-zA-Z]+\b", query)
    return len(entities) >= 2


def is_vague_query(query: str) -> bool:
    return query.strip().lower() in {
        "tell me more",
        "explain more",
        "more details",
        "continue",
        "go on",
    }


def is_reset_query(query: str) -> bool:
    return query.strip().lower() in {
        "new topic",
        "reset",
        "clear context",
        "start over",
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
# Request / State
# =====================================================

conversation_store = {}


class QueryRequest(BaseModel):
    query: str
    conversation_id: str
    # Optional for backward compatibility (CI / CLI)
    tenant_id: Optional[str] = None
    debug: bool = False


@app.get("/health")
def health_check():
    return {"status": "ok"}


# =====================================================
# Guided Fallback helpers
# =====================================================

_VERB_RE = re.compile(
    r"\b(is|are|was|were|be|being|been|shows|show|indicates|indicate|"
    r"communicates|communicate|uses|use|aims|aim|seeks|seek|"
    r"provides|provide|reveals|reveal|demonstrates|demonstrate)\b",
    flags=re.IGNORECASE,
)


def _first_complete_sentence(text: str) -> str | None:
    parts = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    for s in parts:
        if s.endswith((".", "!", "?")):
            return s.strip()
    return None


def build_bullet_highlights(relevant, max_items: int = 4, min_len: int = 40):
    seen = set()
    bullets = []

    for r in sorted(relevant, key=lambda x: x["score"]):
        key = (r["source"], r["page"])
        if key in seen:
            continue
        seen.add(key)

        sent = _first_complete_sentence(r["content"])
        if not sent or len(sent) < min_len or not _VERB_RE.search(sent):
            continue

        bullets.append({
            "highlight": sent,
            "source": r["source"],
            "page": r["page"],
        })

        if len(bullets) >= max_items:
            break

    if not bullets:
        for r in sorted(relevant, key=lambda x: x["score"]):
            sent = _first_complete_sentence(r["content"])
            if sent:
                bullets.append({
                    "highlight": sent,
                    "source": r["source"],
                    "page": r["page"],
                })
                break

    return bullets


# =====================================================
# Main endpoint
# =====================================================

@app.post("/query")
def query_docs(payload: QueryRequest):
    original_query = payload.query

    tenant_id = payload.tenant_id or "default"
    conversation_id = payload.conversation_id

    # -------- RESET CONTEXT --------
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

    state = conversation_store.setdefault(
        (tenant_id, conversation_id),
        {"last_successful_query": None}
    )

    rewritten_query = original_query
    if len(original_query.split()) <= 6 and state["last_successful_query"]:
        rewritten_query = f"In the context of {state['last_successful_query']}, {original_query}"

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

    raw_results, retrieve_status = retrieve(
        rewritten_query,
        k=6,
        tenant_id=tenant_id,
        return_status=True
    )

    results = dedupe_results(raw_results)

    if retrieve_status == "no_documents_ingested":
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
    passed_threshold = best_score <= MAX_DISTANCE

    relevant = [
        {
            "score": round(score, 4),
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page", "unknown"),
            "content": doc.page_content[:600],
        }
        for doc, score in results
    ]

    if is_explanatory_query(original_query) or not passed_threshold:
        bullets = build_bullet_highlights(relevant)
        return wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="guided_fallback",
            answer="",
            citations=citations_from_bullets(bullets),
            artifacts={
                "reason": "No direct answer was found in the documents for this question.",
                "related_highlights": bullets,
            },
            debug=None,
        )

    primary_source = min(relevant, key=lambda r: r["score"])["source"]
    primary_contexts = [r for r in relevant if r["source"] == primary_source]

    answer = generate_answer(rewritten_query, primary_contexts)
    state["last_successful_query"] = original_query

    citations = dedupe_citations(primary_contexts)

    return wrap_response(
        tenant_id=tenant_id,
        conversation_id=conversation_id,
        query=original_query,
        mode="direct_answer",
        answer=answer,
        citations=citations,
        artifacts={"additional_resources": []},
        debug=None,
    )
