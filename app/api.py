from fastapi import FastAPI
from pydantic import BaseModel
import re

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
# Implement “Additional resources” for Direct Answer
# =====================================================

_STOPWORDS = {
    "the","a","an","and","or","to","of","in","on","for","with","as","at","by",
    "is","are","was","were","be","been","being","this","that","these","those",
    "it","its","their","they","them","from","into","about","over","under",
}

def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {w for w in words if w and w not in _STOPWORDS}

def _best_sentence_from_chunk(content: str) -> str | None:
    sent = _first_complete_sentence(content)
    if not sent:
        return None
    # Keep it extractive and “statement-like”
    if len(sent) < 25:
        return None
    return sent.strip()

def _is_redundant_confirmation(
    primary_answer: str,
    candidate_sentence: str,
    min_overlap: float = 0.6
) -> bool:
    a = _tokenize(primary_answer)
    b = _tokenize(candidate_sentence)
    if not a or not b:
        return False
    overlap = len(a.intersection(b)) / max(1, len(a))
    return overlap >= min_overlap


# =====================================================
# Main endpoint
# =====================================================

@app.post("/query")
def query_docs(payload: QueryRequest):
    original_query = payload.query

    # -------- RESET CONTEXT (HARD CONTROL) --------
    if is_reset_query(original_query):
        conversation_store.pop(payload.conversation_id, None)
        return {
            "query": original_query,
            "mode": "hard_refusal",
            "answer": "Context has been reset. Please ask a new question.",
            "citations": [],
            "debug": None,
        }

    state = conversation_store.setdefault(
        payload.conversation_id,
        {"last_successful_query": None}
    )

    rewritten_query = original_query
    if len(original_query.split()) <= 6 and state["last_successful_query"]:
        rewritten_query = f"In the context of {state['last_successful_query']}, {original_query}"

    # Vague query refusal
    if is_vague_query(original_query):
        return {
            "query": original_query,
            "mode": "hard_refusal",
            "answer": refusal_message("no_chunks"),
            "citations": [],
            "debug": None,
        }

    # External comparison refusal
    if mentions_external_entity(original_query):
        return {
            "query": original_query,
            "mode": "hard_refusal",
            "answer": refusal_message("external_entity"),
            "citations": [],
            "debug": None,
        }

    # Retrieval
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
        return {
            "query": original_query,
            "mode": "guided_fallback",
            "no_direct_answer_reason": "No direct answer was found in the documents for this question.",
            "related_highlights": bullets,
            "citations": citations_from_bullets(bullets),
            "debug": debug_payload if payload.debug else None,
        }

    # Defensive guard — should never hit Direct Answer with empty relevant

    if not relevant:
        return {
            "query": original_query,
            "mode": "hard_refusal",
            "answer": refusal_message("no_chunks"),
            "citations": [],
            "debug": debug_payload if payload.debug else None,
        }

    # -------------------------
    # Direct Answer (Primary PDF only)
    # -------------------------
    primary_source = min(relevant, key=lambda r: r["score"])["source"]
    primary_contexts = [r for r in relevant if r["source"] == primary_source]

    answer = generate_answer(rewritten_query, primary_contexts)
    state["last_successful_query"] = original_query

    # -------------------------
    # Additional resources (redundant confirmations)
    # -------------------------
    additional_resources = []
    seen_sources = {primary_source}

    # Consider other sources that also passed threshold (already ensured by passed_threshold)
    for r in relevant:
        src = r["source"]
        if src in seen_sources:
            continue
        seen_sources.add(src)

        sent = _best_sentence_from_chunk(r["content"])
        if not sent:
            continue

        # Deterministic redundancy check (no LLM, no synthesis)
        if not _is_redundant_confirmation(answer, sent, min_overlap=0.6):
            continue

        additional_resources.append({
            "highlight": sent,
            "source": r["source"],
            "page": r["page"],
        })

        if len(additional_resources) >= 5:
            break

    # Citations should include primary + any additional confirmations
    citations = dedupe_citations(primary_contexts) + citations_from_bullets(additional_resources)
    # Deduplicate citations list (safe)
    seen = set()
    deduped = []
    for c in citations:
        key = (c["source"], c["page"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    return {
        "query": original_query,
        "mode": "direct_answer",
        "answer": answer,
        "citations": deduped,
        "additional_resources": additional_resources,
        "debug": debug_payload if payload.debug else None,
    }

