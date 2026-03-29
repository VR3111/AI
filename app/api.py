import os
import re
import uuid
import sqlite3
import smtplib
import logging
import traceback
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Optional, Any

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.llm import generate_answer
from app.retrieve import retrieve, dedupe_results, MAX_DISTANCE
from app.persist import save_query_result, transfer_conversations, delete_tenant_data
from app.read_api import router as read_router
from app.auth import (
    auth_middleware,
    resolve_request_identity,
    get_guest_session_payload,
    issue_guest_session,
    issue_guest_upgrade_ticket,
    decode_guest_upgrade_ticket,
    get_authenticated_user,
    delete_supabase_user,
    set_guest_session_cookie,
    clear_guest_session_cookie,
    build_session_response,
)

# -----------------------------------------------------
# App + CI mode
# -----------------------------------------------------
CI_MODE = os.getenv("CI") == "true"

app = FastAPI(title="Internal Assistant API")

from fastapi.middleware.cors import CORSMiddleware

CORS_ALLOW_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "P1_CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(read_router)

auth_middleware(app)


class GuestUpgradeTicketRequest(BaseModel):
    email: str


class GuestUpgradeRequest(BaseModel):
    ticket: str

# -----------------------------------------------------
# Health
# -----------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/auth/session")
def get_auth_session(request: Request):
    try:
        payload = resolve_request_identity(request)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    if not payload:
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})

    pending_guest = None
    if payload.get("identity_type") != "guest":
        guest_payload = get_guest_session_payload(request)
        if guest_payload:
            pending_guest = str(guest_payload.get("guest_tenant_id") or guest_payload.get("tenant_id"))

    return build_session_response(payload, pending_guest_tenant_id=pending_guest)


@app.post("/auth/guest-session")
def create_or_reuse_guest_session(request: Request):
    try:
        payload = resolve_request_identity(request)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    if payload and payload.get("identity_type") != "guest":
        response = JSONResponse(content=build_session_response(payload))
        return response

    if not payload:
        token, payload = issue_guest_session()
        response = JSONResponse(content=build_session_response(payload))
        set_guest_session_cookie(response, token)
        return response

    return build_session_response(payload)


@app.post("/auth/guest-session/upgrade-ticket")
def create_guest_upgrade_ticket(
    payload: GuestUpgradeTicketRequest,
    request: Request,
):
    try:
        identity_payload = resolve_request_identity(request)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    if not identity_payload or identity_payload.get("identity_type") != "guest":
        return JSONResponse(status_code=401, content={"detail": "Guest session required"})

    try:
        ticket = issue_guest_upgrade_ticket(
            guest_payload=identity_payload,
            email=payload.email,
        )
    except ValueError as error:
        return JSONResponse(status_code=400, content={"detail": str(error)})

    return {
        "status": "issued",
        "ticket": ticket,
        "guest_tenant_id": identity_payload.get("guest_tenant_id") or identity_payload.get("tenant_id"),
    }


@app.post("/auth/guest-session/upgrade")
def prepare_guest_session_upgrade(
    payload: GuestUpgradeRequest,
    request: Request,
):
    try:
        authenticated_payload = resolve_request_identity(request)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    if not authenticated_payload or authenticated_payload.get("identity_type") == "guest":
        return JSONResponse(status_code=401, content={"detail": "Authenticated user required"})

    try:
        ticket_payload = decode_guest_upgrade_ticket(payload.ticket)
        authenticated_user = get_authenticated_user(request)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid guest upgrade ticket"})

    # Merge rules:
    # - Existing-account sign-in never merges because it has no valid signup ticket.
    # - Guest signup can merge after verification on the first authenticated login
    #   only when the signed ticket email matches and the account did not exist
    #   before the ticket was issued.
    # - After a successful merge, the client clears the stored ticket so the move
    #   only happens once.
    ticket_email = str(ticket_payload.get("email") or "").strip().lower()
    user_email = str(authenticated_user.get("email") or "").strip().lower()
    if not ticket_email or not user_email or ticket_email != user_email:
        return JSONResponse(status_code=403, content={"detail": "Guest upgrade email mismatch"})

    user_created_at = authenticated_user.get("created_at")
    if not isinstance(user_created_at, str) or not user_created_at:
        return JSONResponse(status_code=403, content={"detail": "Unable to validate account age"})

    created_timestamp = datetime.fromisoformat(
        user_created_at.replace("Z", "+00:00")
    ).timestamp()
    ticket_issued_at = float(ticket_payload.get("iat") or 0)
    if created_timestamp + 5 < ticket_issued_at:
        return JSONResponse(status_code=403, content={"detail": "Guest upgrade is only available for new accounts"})

    guest_tenant_id = str(ticket_payload.get("guest_tenant_id") or "")
    target_tenant_id = str(authenticated_payload.get("tenant_id"))
    transferred_count = transfer_conversations(
        source_tenant_id=guest_tenant_id,
        target_tenant_id=target_tenant_id,
    )

    response = JSONResponse(
        content={
            "status": (
                "transferred"
                if transferred_count > 0
                else "skipped" if transferred_count < 0 else "ready"
            ),
            "guest_tenant_id": guest_tenant_id,
            "guest_user_id": ticket_payload.get("guest_user_id"),
            "target_tenant_id": target_tenant_id,
            "target_user_id": authenticated_payload.get("sub") or authenticated_payload.get("id"),
        }
    )

    guest_payload = get_guest_session_payload(request)
    guest_cookie_tenant_id = (
        str(guest_payload.get("guest_tenant_id") or guest_payload.get("tenant_id"))
        if guest_payload
        else None
    )
    if transferred_count >= 0 and guest_cookie_tenant_id == guest_tenant_id:
        clear_guest_session_cookie(response)
    return response


@app.delete("/auth/account")
def delete_account(request: Request):
    try:
        authenticated_payload = resolve_request_identity(request)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

    if not authenticated_payload or authenticated_payload.get("identity_type") == "guest":
        return JSONResponse(status_code=401, content={"detail": "Authenticated user required"})

    identity_payload = getattr(request.state, "identity_payload", None) or authenticated_payload
    tenant_id = str(getattr(request.state, "tenant_id", "") or identity_payload.get("tenant_id") or "")

    try:
        authenticated_user = get_authenticated_user(request)
    except Exception:
        return JSONResponse(status_code=401, content={"detail": "Invalid authenticated user session"})

    user_id = str(authenticated_user.get("id") or identity_payload.get("sub") or identity_payload.get("id") or "")
    if not user_id or not tenant_id:
        return JSONResponse(status_code=400, content={"detail": "Authenticated account is missing identifiers"})

    try:
        delete_supabase_user(user_id)
        delete_tenant_data(tenant_id)
    except RuntimeError as error:
        return JSONResponse(status_code=501, content={"detail": str(error)})
    except Exception as e:
        logger.exception("DELETE /auth/account failed for user_id=%s tenant_id=%s", user_id, tenant_id)
        return JSONResponse(status_code=500, content={"detail": "Failed to delete account"})

    response = JSONResponse(content={"status": "deleted"})
    clear_guest_session_cookie(response)
    return response


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


SUPPORT_EMAIL_TO = os.getenv("P1_SUPPORT_EMAIL_TO", "vkrl3111@gmail.com")
SUPPORT_EMAIL_FROM = os.getenv("P1_SUPPORT_EMAIL_FROM")
SUPPORT_SMTP_HOST = os.getenv("P1_SUPPORT_SMTP_HOST")
SUPPORT_SMTP_PORT = int(os.getenv("P1_SUPPORT_SMTP_PORT", "587"))
SUPPORT_SMTP_USERNAME = os.getenv("P1_SUPPORT_SMTP_USERNAME")
SUPPORT_SMTP_PASSWORD = os.getenv("P1_SUPPORT_SMTP_PASSWORD")
SUPPORT_SMTP_USE_TLS = os.getenv("P1_SUPPORT_SMTP_USE_TLS", "true").lower() != "false"


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


class SupportRequest(BaseModel):
    request_type: str
    subject: str
    contact_email: str
    details: str
    conversation_id: Optional[str] = None
    client_timestamp: str


def _send_support_email(
    *,
    tenant_id: str,
    payload: SupportRequest,
    server_timestamp: str,
) -> None:
    if not SUPPORT_SMTP_HOST or not SUPPORT_EMAIL_FROM:
        raise RuntimeError("Support email delivery is not configured on the server.")

    subject = f"[P1 {payload.request_type.title()}] {payload.subject.strip()}"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SUPPORT_EMAIL_FROM
    message["To"] = SUPPORT_EMAIL_TO
    message["Reply-To"] = payload.contact_email.strip()

    message.set_content(
        "\n".join(
            [
                "P1 Support Request",
                "",
                f"Request type: {payload.request_type}",
                f"Tenant: {tenant_id}",
                f"Contact email: {payload.contact_email.strip()}",
                f"Conversation ID: {payload.conversation_id or 'N/A'}",
                f"Client timestamp: {payload.client_timestamp}",
                f"Server timestamp: {server_timestamp}",
                "",
                "Details:",
                payload.details.strip(),
            ]
        )
    )

    with smtplib.SMTP(SUPPORT_SMTP_HOST, SUPPORT_SMTP_PORT, timeout=20) as smtp:
        smtp.ehlo()
        if SUPPORT_SMTP_USE_TLS:
            smtp.starttls()
            smtp.ehlo()
        if SUPPORT_SMTP_USERNAME and SUPPORT_SMTP_PASSWORD:
            smtp.login(SUPPORT_SMTP_USERNAME, SUPPORT_SMTP_PASSWORD)
        smtp.send_message(message)


# =====================================================
# Query classification helpers
# =====================================================
def is_explanatory_query(query: str) -> bool:
    return bool(re.match(r"^\s*(how(?!\s+many\b)|why|in what way|in which way)\b", query, re.I))


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
# Citations builder
# =====================================================
def _wants_exact_answer(query: str) -> bool:
    return bool(
        re.search(
            r"\bquote\b|\bexact(?:ly)?\b|\bverbatim\b|\bamount\b|as written",
            query,
            re.I,
        )
    )


QUESTION_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "any",
    "there",
    "document",
    "card",
    "agreement",
    "american",
    "express",
    "gold",
    "what",
    "how",
    "many",
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "within",
    "before",
    "after",
    "apply",
    "applicable",
    "written",
    "exactly",
    "quote",
    "answer",
}


def _wants_bounded_answer(query: str) -> bool:
    return bool(
        re.search(
            r"\bhow many\b|\blimit\b|\bmaximum\b|\bminimum\b|\bfee\b|\bamount\b|\bthreshold\b|\bcount\b|\bwithin\b|\bbefore\b|\bafter\b",
            query,
            re.I,
        )
    )


def _normalize_for_match(text: str) -> str:
    normalized = text.lower().replace("-\n", "").replace("\n", " ")
    normalized = re.sub(r"[^a-z0-9$]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _content_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for token in re.findall(r"[a-z0-9]+", _normalize_for_match(text)):
        if len(token) <= 2 or token in QUESTION_STOPWORDS:
            continue
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        if token not in tokens:
            tokens.append(token)
    return tokens


def _focus_phrase_variants(focus_phrase: str | None) -> list[str]:
    if not focus_phrase:
        return []

    variants: list[str] = []
    base = focus_phrase.strip().lower()
    for candidate in (
        base,
        re.sub(r"\bfees?\b$", "", base).strip(),
        re.sub(r"\b(?:within|before|after|when|if)\b.+$", "", base).strip(),
        re.split(r"\b(?:is|are|was|were|can|could|should)\b", base, 1)[0].strip(),
    ):
        if not candidate or candidate in variants:
            continue
        if candidate != focus_phrase.strip().lower() and len(candidate.split()) < 2:
            continue
        variants.append(candidate)
    return variants


def _find_field_value_start(text: str, focus_phrase: str | None) -> int | None:
    for variant in _focus_phrase_variants(focus_phrase):
        patterns = [
            re.compile(
                r"\b"
                + r"\s+".join(re.escape(token) for token in variant.split())
                + r"\b\s*:\s*([^\n]{1,120})",
                re.I,
            ),
            re.compile(
                r"\b"
                + r"\s+".join(re.escape(token) for token in variant.split())
                + r"\b\s+((?:up to\s+)?\$\s*\d[\d,]*(?:\.\d+)?|none\b|no\s+ne\b)",
                re.I,
            ),
        ]

        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue

            value = match.group(1).strip()
            if not value:
                continue

            if re.match(r"(this fee|the fee|please refer)\b", value, re.I):
                continue

            return match.start()

    return None


def _build_snippet(text: str, query: str) -> str:
    if not text:
        return ""

    lowered = text.lower()
    focus_phrase = _extract_focus_phrase(query)
    wants_exact_value = _wants_exact_answer(query)
    wants_bounded_answer = _wants_bounded_answer(query)
    focus_tokens = (
        _content_tokens(" ".join(_focus_phrase_variants(focus_phrase)))
        if focus_phrase
        else _content_tokens(query)
    )

    snippet_start = 0
    field_value_start = _find_field_value_start(text, focus_phrase)
    if field_value_start is not None:
        snippet_start = max(field_value_start - 80, 0)
    elif focus_phrase:
        for variant in _focus_phrase_variants(focus_phrase):
            focus_index = lowered.find(variant)
            if focus_index >= 0:
                snippet_start = max(focus_index - 80, 0)
                break
        if snippet_start == 0 and wants_bounded_answer:
            for token in focus_tokens:
                focus_index = lowered.find(token)
                if focus_index >= 0:
                    snippet_start = max(focus_index - 80, 0)
                    break
    elif wants_exact_value:
        amount_match = re.search(r"\$\s*\d[\d,]*(?:\.\d+)?", text)
        if amount_match:
            snippet_start = max(amount_match.start() - 80, 0)

    return text[snippet_start:snippet_start + 300]


def build_citations(results: list[tuple[Any, float]], query: str) -> list[dict]:
    citations: list[dict] = []
    for doc, score in results:
        citations.append(
            {
                "source": doc.metadata.get("source"),
                "page": doc.metadata.get("page"),
                "score": score,
                "snippet": _build_snippet(doc.page_content or "", query),
            }
        )
    return citations


def _source_display_name(source: Any) -> str:
    source_text = str(source or "").strip()
    if not source_text:
        return "Unknown source"
    return os.path.basename(source_text)


def _normalize_source_match_text(text: str) -> str:
    normalized = text.lower()
    normalized = re.sub(r"\.[a-z0-9]+$", "", normalized)
    normalized = re.sub(r"[-_]+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _query_mentions_document(query: str, doc: Any) -> bool:
    normalized_query = _normalize_source_match_text(query)
    if not normalized_query:
        return False

    terms: list[str] = []
    source_name = _normalize_source_match_text(_source_display_name(doc.metadata.get("source")))
    if source_name:
        terms.append(source_name)

    title = _normalize_source_match_text(str(doc.metadata.get("title") or ""))
    if title and title not in terms:
        terms.append(title)

    return any(term and len(term) >= 4 and term in normalized_query for term in terms)


def _document_query_terms(doc: Any) -> list[str]:
    terms: list[str] = []
    for candidate in (
        _normalize_source_match_text(_source_display_name(doc.metadata.get("source"))),
        _normalize_source_match_text(str(doc.metadata.get("title") or "")),
    ):
        if not candidate:
            continue
        if candidate not in terms:
            terms.append(candidate)
        without_trailing_numbers = re.sub(r"(?:\s+\d+)+$", "", candidate).strip()
        if without_trailing_numbers and without_trailing_numbers not in terms:
            terms.append(without_trailing_numbers)
    return terms


def _strip_document_reference_from_query(query: str, doc: Any) -> str:
    stripped = query
    for term in sorted(_document_query_terms(doc), key=len, reverse=True):
        tokens = [token for token in term.split() if token]
        if not tokens:
            continue
        pattern = r"\b" + r"[\s\-_]+".join(re.escape(token) for token in tokens) + r"\b"
        stripped = re.sub(pattern, "", stripped, flags=re.I)

    stripped = re.sub(r"\bfor\s+(?:the\s+)?(?=[?.!,;:]|$)", "", stripped, flags=re.I)
    stripped = re.sub(r"\s+", " ", stripped)
    stripped = re.sub(r"\s+([?.!,;:])", r"\1", stripped).strip()
    return stripped or query


def _filter_results_to_source(
    results: list[tuple[Any, float]],
    source: str,
) -> list[tuple[Any, float]]:
    return [
        (doc, score)
        for doc, score in results
        if str(doc.metadata.get("source") or "") == source
    ]


def _best_result_per_source(results: list[tuple[Any, float]]) -> list[tuple[Any, float]]:
    best_by_source: dict[str, tuple[Any, float]] = {}
    for doc, score in results:
        source = str(doc.metadata.get("source") or "")
        if not source:
            continue
        current = best_by_source.get(source)
        if current is None or score < current[1]:
            best_by_source[source] = (doc, score)
    return list(best_by_source.values())


def _extract_focus_phrase(query: str) -> str | None:
    cleaned = query.strip().lower()
    cleaned = re.sub(r"^\s*in\s+the\s+.+?\s+document,\s*", "", cleaned)
    cleaned = cleaned.split("?", 1)[0]
    cleaned = re.sub(r"\b(?:quote|answer|respond)\b.+$", "", cleaned).strip()

    patterns = [
        r"^what is the (.+)$",
        r"^what is (.+)$",
        r"^what are the (.+)$",
        r"^how many (.+)$",
        r"^what does .+? say about (.+)$",
        r"^is there (?:any |a |an )?(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, cleaned)
        if match:
            phrase = match.group(1).strip(" .,:;")
            return phrase or None
    return None


def _rerank_results(query: str, results: list[tuple[Any, float]]) -> list[tuple[Any, float]]:
    focus_phrase = _extract_focus_phrase(query)
    wants_exact_value = _wants_exact_answer(query)
    wants_bounded_answer = _wants_bounded_answer(query)
    focus_tokens = (
        _content_tokens(" ".join(_focus_phrase_variants(focus_phrase)))
        if focus_phrase
        else _content_tokens(query)
    )

    reranked: list[tuple[Any, float, float]] = []
    for doc, score in results:
        text = (doc.page_content or "").lower()
        normalized_text = _normalize_for_match(doc.page_content or "")
        adjusted_score = score
        has_focus_phrase = bool(focus_phrase and focus_phrase in text)
        matched_focus_tokens = [token for token in focus_tokens if token in normalized_text]
        focus_token_coverage = (
            len(matched_focus_tokens) / len(focus_tokens)
            if focus_tokens
            else 0.0
        )
        has_focus_tokens = focus_token_coverage >= 0.6
        has_dollar_amount = bool(re.search(r"\$\s*\d", doc.page_content or ""))
        has_numeric_value = bool(
            re.search(r"\$\s*\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\b", doc.page_content or "")
        )
        has_condition_language = bool(
            re.search(r"\bwithin\b|\bbefore\b|\bafter\b|\bif\b|\bunless\b|\buntil\b|\bthereafter\b|\bfree\b", normalized_text)
        )
        field_value_start = _find_field_value_start(doc.page_content or "", focus_phrase)
        has_field_value = field_value_start is not None
        has_field_label = any(
            re.search(
                r"\b" + r"\s+".join(re.escape(token) for token in variant.split()) + r"\b\s*:",
                doc.page_content or "",
                re.I,
            )
            for variant in _focus_phrase_variants(focus_phrase)
        )

        if has_field_value:
            adjusted_score -= 0.45
        elif has_field_label:
            adjusted_score -= 0.25
        elif has_focus_phrase:
            adjusted_score -= 0.35
        elif has_focus_tokens:
            adjusted_score -= 0.20

        if focus_token_coverage >= 0.8:
            adjusted_score -= 0.30
        elif focus_token_coverage >= 0.5:
            adjusted_score -= 0.15

        if wants_exact_value and has_dollar_amount:
            adjusted_score -= 0.15

        if wants_exact_value and (has_field_value or has_focus_phrase or has_focus_tokens) and has_dollar_amount:
            adjusted_score -= 0.20

        if wants_bounded_answer and has_numeric_value and focus_token_coverage >= 0.35:
            adjusted_score -= 0.35

        if wants_bounded_answer and has_condition_language and focus_token_coverage >= 0.35:
            adjusted_score -= 0.10

        if wants_bounded_answer and has_numeric_value and has_condition_language and focus_token_coverage >= 0.35:
            adjusted_score -= 0.20

        reranked.append((doc, score, max(adjusted_score, 0.0)))

    reranked.sort(key=lambda item: item[2])
    return [(doc, score) for doc, score, _adjusted_score in reranked]


def _has_strong_answer_evidence(query: str, text: str) -> bool:
    focus_phrase = _extract_focus_phrase(query)
    focus_tokens = (
        _content_tokens(" ".join(_focus_phrase_variants(focus_phrase)))
        if focus_phrase
        else _content_tokens(query)
    )
    normalized_text = _normalize_for_match(text)
    matched_focus_tokens = [token for token in focus_tokens if token in normalized_text]
    focus_token_coverage = (
        len(matched_focus_tokens) / len(focus_tokens)
        if focus_tokens
        else 0.0
    )

    has_field_value = _find_field_value_start(text, focus_phrase) is not None
    has_numeric_value = bool(
        re.search(r"\$\s*\d[\d,]*(?:\.\d+)?|\b\d[\d,]*(?:\.\d+)?\b", text)
    )
    has_condition_language = bool(
        re.search(r"\bwithin\b|\bbefore\b|\bafter\b|\bif\b|\bunless\b|\buntil\b|\bthereafter\b|\bfree\b", normalized_text)
    )

    if _wants_bounded_answer(query):
        return has_field_value and has_numeric_value

    if has_field_value:
        return True

    return False


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
                debug={"reset": True} if payload.debug else None,
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
                debug={"reason": "vague_query"} if payload.debug else None,
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
                debug={"reason": "external_entity"} if payload.debug else None,
            )
        )

    # ---------------- retrieval ----------------
    raw_results, status = retrieve(
        rewritten_query, k=15, tenant_id=tenant_id, return_status=True
    )
    raw_distance_results = dedupe_results(raw_results)
    selection_query = original_query
    explicit_source_docs = {
        str(doc.metadata.get("source") or ""): doc
        for doc, _score in raw_distance_results
        if _query_mentions_document(original_query, doc)
    }
    if len(explicit_source_docs) == 1:
        selected_source, selected_doc = next(iter(explicit_source_docs.items()))
        raw_distance_results = _filter_results_to_source(raw_distance_results, selected_source)
        selection_query = _strip_document_reference_from_query(original_query, selected_doc)
    results = _rerank_results(selection_query, raw_distance_results)
    in_distance_keys = {
        (
            doc.page_content.strip(),
            doc.metadata.get("source"),
            doc.metadata.get("page"),
        )
        for doc, score in raw_distance_results
        if score <= MAX_DISTANCE
    }
    in_distance_results = [
        (doc, score)
        for doc, score in results
        if (
            doc.page_content.strip(),
            doc.metadata.get("source"),
            doc.metadata.get("page"),
        ) in in_distance_keys
    ]
    strong_evidence_results = [
        (doc, score)
        for doc, score in in_distance_results
        if _has_strong_answer_evidence(selection_query, doc.page_content or "")
    ]
    evidence_results = (strong_evidence_results or in_distance_results or results)[:3]

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
                debug={"status": status} if payload.debug else None,
            )
        )

    if not evidence_results:
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer=refusal_message("no_chunks"),
                citations=[],
                artifacts={"reason": "no_chunks"},
                debug={
                    "status": status,
                    "rewritten_query": rewritten_query,
                    "results_count": 0,
                }
                if payload.debug
                else None,
            )
        )

    best_score = min(score for _, score in raw_distance_results)
    citations = build_citations(evidence_results, original_query)
    has_strong_evidence = bool(strong_evidence_results)
    plausible_source_results = _best_result_per_source(strong_evidence_results or in_distance_results)

    if len(plausible_source_results) >= 2:
        ambiguity_citations = build_citations(plausible_source_results[:3], original_query)
        matched_documents = [
            _source_display_name(doc.metadata.get("source"))
            for doc, _score in plausible_source_results
        ]
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="guided_fallback",
                answer="I found this information in multiple documents. Choose a document or ask me to compare them.",
                citations=ambiguity_citations,
                artifacts={
                    "reason": "multiple_documents_match",
                    "matched_documents": matched_documents,
                },
                debug={
                    "rewritten_query": rewritten_query,
                    "best_score": best_score,
                    "max_distance": MAX_DISTANCE,
                    "matched_documents": matched_documents,
                    "results_count": len(plausible_source_results),
                }
                if payload.debug
                else None,
            )
        )

    # ---------------- fallback logic ----------------
    # IMPORTANT CHANGE:
    # - If we HAVE chunks, we should NOT return blank answer.
    # - We will still show citations + chunk evidence.
    if is_explanatory_query(original_query) or (
        best_score > MAX_DISTANCE and not has_strong_evidence
    ):
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="guided_fallback",
                answer="No direct answer was found verbatim in the documents. Try asking more specifically, or use keywords from the document.",
                citations=citations,
                artifacts={
                    "reason": "No direct answer was found in the documents for this question.",
                    "best_score": best_score,
                },
                debug={
                    "rewritten_query": rewritten_query,
                    "best_score": best_score,
                    "max_distance": MAX_DISTANCE,
                    "results_count": len(evidence_results),
                }
                if payload.debug
                else None,
            )
        )

    # ---------------- direct answer ----------------
    contexts = [
        {
            "content": doc.page_content,
            "source": doc.metadata.get("source"),
            "page": doc.metadata.get("page"),
        }
        for doc, _score in evidence_results
    ]

    answer = generate_answer(original_query, contexts)

    return persist_and_return(
        wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="direct_answer",
            answer=answer,
            citations=citations,
            artifacts={"additional_resources": [], "best_score": best_score},
            debug={
                "rewritten_query": rewritten_query,
                "best_score": best_score,
                "max_distance": MAX_DISTANCE,
                "results_count": len(evidence_results),
            }
            if payload.debug
            else None,
            )
        )


@app.post("/support/requests")
def submit_support_request(payload: SupportRequest, request: Request):
    tenant_id = request.state.tenant_id
    server_timestamp = now_iso()

    request_type = payload.request_type.strip().lower()
    if request_type not in {"issue", "feature", "contact"}:
        raise HTTPException(status_code=400, detail="Invalid support request type")

    subject = payload.subject.strip()
    contact_email = payload.contact_email.strip()
    details = payload.details.strip()

    if not subject:
        raise HTTPException(status_code=400, detail="Subject is required")
    if not contact_email:
        raise HTTPException(status_code=400, detail="Contact email is required")
    if not details:
        raise HTTPException(status_code=400, detail="Details are required")

    try:
        _send_support_email(
            tenant_id=tenant_id,
            payload=payload,
            server_timestamp=server_timestamp,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except smtplib.SMTPException:
        raise HTTPException(
            status_code=502,
            detail="Support request delivery failed. Please try again.",
        )

    return {
        "status": "sent",
        "request_type": request_type,
        "recipient": SUPPORT_EMAIL_TO,
        "tenant_id": tenant_id,
        "conversation_id": payload.conversation_id,
        "timestamp": server_timestamp,
    }
