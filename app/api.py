from fastapi import FastAPI
from pydantic import BaseModel
import re
import os

from app.llm import generate_answer
from app.retrieve import retrieve, dedupe_results, MAX_DISTANCE

app = FastAPI(title="Internal Assistant API")

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
        unique.append({"source": r["source"], "page": r["page"]})
    return unique


def citations_from_bullets(bullets):
    seen = set()
    out = []
    for b in bullets:
        key = (b["source"], b["page"])
        if key not in seen:
            seen.add(key)
            out.append({"source": b["source"], "page": b["page"]})
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


def mentions_external_entity(query: str, sources: list) -> bool:
    comparison_keywords = {"better", "worse", "than", "vs", "versus", "compare"}
    words = set(re.findall(r"\b\w+\b", query.lower()))
    if not words.intersection(comparison_keywords):
        return False

    known_text = " ".join(sources).lower()
    entities = re.findall(r"\b[A-Z][a-zA-Z]+\b", query)

    for e in entities:
        if e.lower() not in known_text:
            return True
    return False


def is_vague_query(query: str) -> bool:
    return query.strip().lower() in {
        "tell me more",
        "explain more",
        "more details",
        "continue",
        "go on",
    }


# =====================================================
# Refusal UX
# =====================================================

def refusal_message(reason: str) -> str:
    if reason == "no_chunks":
        return "Please provide more context so I can answer accurately."
    return "The documents do not answer this question."


# =====================================================
# Request / State
# =====================================================

conversation_store = {}

class QueryRequest(BaseModel):
    query: str
    conversation_id: str
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
    state = conversation_store.setdefault(
        payload.conversation_id,
        {"last_successful_query": None}
    )

    original_query = payload.query
    rewritten_query = payload.query

    if len(original_query.split()) <= 6 and state["last_successful_query"]:
        rewritten_query = f"In the context of {state['last_successful_query']}, {original_query}"

    if is_vague_query(original_query):
        return {
            "query": original_query,
            "mode": "hard_refusal",
            "answer": refusal_message("no_chunks"),
            "citations": [],
            "debug": None,
        }

    raw_results = retrieve(rewritten_query, k=6)
    results = dedupe_results(raw_results)

    debug_payload = None
    if payload.debug:
        debug_payload = {
            "original_query": original_query,
            "rewritten_query": rewritten_query,
            "max_distance_threshold": MAX_DISTANCE,
            "retrieval_scores": [
                {
                    "source": doc.metadata.get("source"),
                    "page": doc.metadata.get("page"),
                    "score": round(score, 4),
                }
                for doc, score in results
            ],
        }

    if not results:
        return {
            "query": original_query,
            "mode": "hard_refusal",
            "answer": refusal_message("no_chunks"),
            "citations": [],
            "debug": debug_payload if payload.debug else None,
        }

    sources_text = [doc.metadata.get("source", "") for doc, _ in results]
    if mentions_external_entity(original_query, sources_text):
        return {
            "query": original_query,
            "mode": "hard_refusal",
            "answer": refusal_message("external_entity"),
            "citations": [],
            "debug": debug_payload if payload.debug else None,
        }

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

    if is_explanatory_query(original_query) or not passed_threshold or not is_definition_query(original_query):
        bullets = build_bullet_highlights(relevant)
        return {
            "query": original_query,
            "mode": "guided_fallback",
            "no_direct_answer_reason": "No direct answer was found in the documents for this question.",
            "related_highlights": bullets,
            "citations": citations_from_bullets(bullets),
            "debug": debug_payload if payload.debug else None,
        }

    answer = generate_answer(rewritten_query, relevant)
    state["last_successful_query"] = original_query

    return {
        "query": original_query,
        "mode": "direct_answer",
        "answer": answer,
        "citations": dedupe_citations(relevant),
        "debug": debug_payload if payload.debug else None,
    }
