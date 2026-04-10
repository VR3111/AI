import os
import re
import uuid
import json
import sqlite3
import smtplib
import logging
import traceback
from dataclasses import dataclass
from types import SimpleNamespace
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
@dataclass(frozen=True)
class ConversationTurnRecord:
    query: str
    mode: str
    artifacts: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class ConversationFollowUpContext:
    kind: str
    source: str | None = None
    source_display_name: str | None = None
    compare_sources: tuple[str, ...] = ()
    compare_display_names: tuple[str, ...] = ()
    compare_field: str | None = None
    anchor_query: str = ""


def get_recent_conversation_turns(
    tenant_id: str,
    conversation_id: str,
    *,
    limit: int = 25,
) -> list[ConversationTurnRecord]:
    db_path = os.path.join("data", "tenants", tenant_id, "p1.db")
    if not os.path.isfile(db_path):
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT query, mode, artifacts_json, created_at
            FROM queries
            WHERE tenant_id = ?
              AND conversation_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (tenant_id, conversation_id, limit),
        ).fetchall()

        turns: list[ConversationTurnRecord] = []
        for row in reversed(rows):
            raw_artifacts = str(row["artifacts_json"] or "").strip()
            artifacts: dict[str, Any] = {}
            if raw_artifacts:
                try:
                    parsed = json.loads(raw_artifacts)
                except json.JSONDecodeError:
                    parsed = {}
                if isinstance(parsed, dict):
                    artifacts = parsed

            turns.append(
                ConversationTurnRecord(
                    query=str(row["query"] or ""),
                    mode=str(row["mode"] or ""),
                    artifacts=artifacts,
                    created_at=str(row["created_at"] or ""),
                )
            )
        return turns
    finally:
        conn.close()


def _last_successful_query_from_turns(
    turns: list[ConversationTurnRecord],
) -> Optional[str]:
    for turn in reversed(turns):
        if turn.mode == "direct_answer" and turn.query.strip():
            return turn.query
    return None


# =====================================================
# Request model
# =====================================================
class QueryRequest(BaseModel):
    query: str
    conversation_id: str
    tenant_id: Optional[str] = None
    selected_source: Optional[str] = None
    compare_sources: Optional[list[str]] = None
    compare_focus_query: Optional[str] = None
    workspace_scope: Optional[str] = None
    follow_up_context: Optional[bool] = True
    compare_follow_up: Optional[bool] = True
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


DOCUMENT_ALIAS_STOPWORDS = {
    "document",
    "documents",
    "doc",
    "docs",
    "agreement",
    "agreements",
    "file",
    "files",
    "pdf",
    "pricing",
    "schedule",
    "rates",
    "fees",
    "table",
    "final",
    "draft",
    "copy",
    "signed",
    "card",
    "cards",
}


TRUSTED_BRAND_ALIASES = {
    "american express": {"amex"},
    "discover": {"discover"},
    "prime": {"prime"},
    "citibank": {"citi"},
    "citi": {"citibank"},
}


def _wants_bounded_answer(query: str) -> bool:
    return bool(
        re.search(
            r"\bhow many\b|\blimit\b|\bmaximum\b|\bminimum\b|\bfee\b|\bamount\b|\bthreshold\b|\bcount\b|\bbalance\b|\bwithin\b|\bbefore\b|\bafter\b|\bapr\b|\bannual percentage rate\b",
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

    apr_variants: list[str] = []
    if base == "apr":
        apr_variants = [
            "annual percentage rate",
            "purchase apr",
            "purchase annual percentage rate",
            "balance transfer apr",
            "balance transfer annual percentage rate",
            "cash advance apr",
            "cash advance annual percentage rate",
        ]
    elif base == "annual percentage rate":
        apr_variants = [
            "apr",
            "purchase apr",
            "purchase annual percentage rate",
            "balance transfer apr",
            "balance transfer annual percentage rate",
            "cash advance apr",
            "cash advance annual percentage rate",
        ]
    elif base == "purchase apr":
        apr_variants = ["purchase annual percentage rate"]
    elif base == "purchase annual percentage rate":
        apr_variants = ["purchase apr"]
    elif base == "balance transfer apr":
        apr_variants = ["balance transfer annual percentage rate"]
    elif base == "balance transfer annual percentage rate":
        apr_variants = ["balance transfer apr"]
    elif base == "cash advance apr":
        apr_variants = ["cash advance annual percentage rate"]
    elif base == "cash advance annual percentage rate":
        apr_variants = ["cash advance apr"]

    for candidate in (
        base,
        re.sub(r"\bannual fee\b", "annual membership fee", base).strip(),
        re.sub(r"\bannual membership fee\b", "annual fee", base).strip(),
        re.sub(r"\blate payment fee\b", "late fee", base).strip(),
        re.sub(r"\blate fee\b", "late payment fee", base).strip(),
        re.sub(r"\bapr\b", "annual percentage rate", base).strip(),
        re.sub(r"\baprs\b", "annual percentage rates", base).strip(),
        re.sub(r"\bfees?\b$", "", base).strip(),
        re.sub(r"\b(?:within|before|after|when|if)\b.+$", "", base).strip(),
        re.split(r"\b(?:is|are|was|were|can|could|should)\b", base, 1)[0].strip(),
        *apr_variants,
    ):
        if not candidate or candidate in variants:
            continue
        if candidate != focus_phrase.strip().lower() and len(candidate.split()) < 2:
            continue
        variants.append(candidate)
    return variants


def _field_value_patterns(variant: str) -> list[re.Pattern[str]]:
    phrase_pattern = r"\b" + r"\s+".join(re.escape(token) for token in variant.split()) + r"\b"
    value_pattern = (
        r"(?:up to\s+)?\$\s*\d[\d,]*(?:\.\d+)?"
        r"|(?:\d+(?:\.\d+)?\s*%)\s*(?:to|-|–|—)\s*(?:\d+(?:\.\d+)?\s*%)"
        r"|(?:\d+(?:\.\d+)?\s*%)"
        r"|none\b|no\s+ne\b"
    )
    return [
        re.compile(phrase_pattern + r"\s*:\s*([^\n]{1,120})", re.I),
        re.compile(phrase_pattern + r"\s+(" + value_pattern + r")", re.I),
    ]


def _normalize_extracted_field_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _has_nearby_value_hint(
    match_suffix: str,
    text: str,
    line_end: int,
    value_hint_pattern: re.Pattern[str],
) -> bool:
    preview = match_suffix[:60]
    if value_hint_pattern.search(preview):
        return True

    if line_end >= len(text):
        return False

    next_line_start = line_end + 1
    next_line_end = text.find("\n", next_line_start)
    if next_line_end < 0:
        next_line_end = len(text)
    next_line = text[next_line_start:next_line_end].strip()
    if not next_line:
        return False

    return bool(value_hint_pattern.search(next_line[:60]))


def _is_non_answer_field_context(
    *,
    focus_phrase: str | None,
    match_prefix: str,
    match_suffix: str,
    value: str,
) -> bool:
    context = _normalize_for_match(f"{match_prefix} {match_suffix} {value}")
    normalized_focus = _normalize_for_match(focus_phrase or "")

    if "additional card" in context or "additional cards" in context:
        return True

    if any(
        token in context
        for token in (
            "rates and fees table",
            "refer to the refund policy",
            "refund policy",
            "closing or suspending your account",
            "voluntarily closing your account",
            "if your account is cancelled",
            "if an annual fee applies",
        )
    ):
        return True

    if normalized_focus == "annual fee" and any(
        token in context
        for token in (
            "non refundable",
            "refund",
            "cancelled",
            "closing date",
            "billing statement",
            "re open it",
            "reopen it",
            "close your account",
        )
    ):
        return True

    return False


def _extract_field_value_from_line(
    text: str,
    focus_phrase: str | None,
) -> tuple[str, int] | None:
    value_hint_pattern = re.compile(
        r"\$\s*\d|\bnone\b|\bno\s+ne\b|\d+(?:\.\d+)?\s*%|\bafter that\b",
        re.I,
    )

    for variant in _focus_phrase_variants(focus_phrase):
        phrase_pattern = re.compile(
            r"\b" + r"\s+".join(re.escape(token) for token in variant.split()) + r"\b",
            re.I,
        )

        for match in phrase_pattern.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            if line_end < 0:
                line_end = len(text)

            line = text[line_start:line_end]
            if not line.strip():
                continue

            match_offset = match.end() - line_start
            match_prefix = line[:match.start() - line_start]
            match_suffix = line[match_offset:].lstrip(" :.-\t")
            if not _has_nearby_value_hint(
                match_suffix,
                text,
                line_end,
                value_hint_pattern,
            ):
                continue

            continuation_end = line_end
            for _ in range(2):
                if (
                    not match_suffix
                    or re.search(r"[.!?]$", match_suffix.strip())
                    or re.search(
                        r"(?:\$\s*\d[\d,]*(?:\.\d+)?|\bnone\b|\bno\s+ne\b|\d+(?:\.\d+)?\s*%)\s*$",
                        match_suffix.strip(),
                        re.I,
                    )
                    or continuation_end >= len(text)
                ):
                    break

                next_line_start = continuation_end + 1
                next_line_end = text.find("\n", next_line_start)
                if next_line_end < 0:
                    next_line_end = len(text)
                next_line = text[next_line_start:next_line_end].strip()
                if not next_line or re.match(
                    r"^(?:[A-Z][a-z]+(?: [A-Z][a-z]+){0,3}(?: Fee| APR| APRs| Charge| Charges)|Fees)\b",
                    next_line,
                ):
                    break

                match_suffix = f"{match_suffix} {next_line}"
                continuation_end = next_line_end
            value = _normalize_extracted_field_value(match_suffix)
            if not value:
                continue

            if re.search(r"\badditional\s+cards?\b|\badditional\s+card\b", match_prefix + " " + value, re.I):
                continue

            if _is_referral_value(value):
                continue

            if _is_non_answer_field_context(
                focus_phrase=focus_phrase,
                match_prefix=match_prefix,
                match_suffix=match_suffix,
                value=value,
            ):
                continue

            if not value_hint_pattern.search(value):
                continue

            return value, match.start()

    return None


def _find_field_value_start(text: str, focus_phrase: str | None) -> int | None:
    line_match = _extract_field_value_from_line(text, focus_phrase)
    if line_match is not None:
        _value, start = line_match
        return start

    for variant in _focus_phrase_variants(focus_phrase):
        for pattern in _field_value_patterns(variant):
            match = pattern.search(text)
            if not match:
                continue

            value = match.group(1).strip()
            if not value:
                continue
            value = _normalize_extracted_field_value(value)

            match_prefix = text[max(match.start() - 30, 0):match.start()]
            if re.search(r"\badditional\s+cards?\b|\badditional\s+card\b", match_prefix, re.I):
                continue

            if _is_referral_value(value):
                continue

            if _is_non_answer_field_context(
                focus_phrase=focus_phrase,
                match_prefix=match_prefix,
                match_suffix=value,
                value=value,
            ):
                continue

            return match.start()

    return None


def _is_referral_value(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip().lower()
    compact = re.sub(r"[^a-z]+", "", normalized)

    if "rates and fees table" in normalized or "ratesandfeestable" in compact:
        return True

    if (
        compact.startswith(("thisfee", "thefee", "pleaserefer", "seepage", "seepart"))
        and any(token in normalized for token in ("page", "part", "table", "schedule"))
    ):
        return True

    return False


def _extract_field_value(text: str, focus_phrase: str | None) -> str | None:
    line_match = _extract_field_value_from_line(text, focus_phrase)
    if line_match is not None:
        value, _start = line_match
        return "None" if re.fullmatch(r"no\s+ne|none", value, re.I) else value

    for variant in _focus_phrase_variants(focus_phrase):
        for pattern in _field_value_patterns(variant):
            match = pattern.search(text)
            if not match:
                continue

            value = match.group(1).strip()
            if not value:
                continue
            value = _normalize_extracted_field_value(value)

            match_prefix = text[max(match.start() - 30, 0):match.start()]
            if re.search(r"\badditional\s+cards?\b|\badditional\s+card\b", match_prefix, re.I):
                continue

            if _is_referral_value(value):
                continue

            if _is_non_answer_field_context(
                focus_phrase=focus_phrase,
                match_prefix=match_prefix,
                match_suffix=value,
                value=value,
            ):
                continue

            return "None" if re.fullmatch(r"no\s+ne|none", value, re.I) else value

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


def _tenant_docs_path(tenant_id: str) -> str:
    return os.path.join("data", "tenants", tenant_id, "docs")


def _tenant_document_sources(tenant_id: str) -> list[str]:
    docs_path = _tenant_docs_path(tenant_id)
    if not os.path.isdir(docs_path):
        return []
    return sorted(
        os.path.join(docs_path, filename)
        for filename in os.listdir(docs_path)
        if filename.lower().endswith(".pdf")
    )


def _sanitize_compare_sources(tenant_id: str, raw_sources: list[str] | None) -> list[str]:
    allowed_sources = set(_tenant_document_sources(tenant_id))
    selected_sources: list[str] = []
    for source in list(raw_sources or []):
        source_text = str(source or "").strip()
        if not source_text or source_text not in allowed_sources or source_text in selected_sources:
            continue
        selected_sources.append(source_text)
    return selected_sources[:2]


def _artifacts_workspace_scope(artifacts: dict[str, Any]) -> str:
    workspace_scope = str(artifacts.get("workspace_scope") or "global").strip().lower()
    return workspace_scope if workspace_scope in {"global", "document"} else "global"


def _compare_sources_from_artifacts(
    artifacts: dict[str, Any],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen_sources: set[str] = set()
    raw_compare_results = artifacts.get("compare_results")
    if not isinstance(raw_compare_results, list):
        return pairs

    for item in raw_compare_results:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        if not source or source in seen_sources:
            continue
        seen_sources.add(source)
        display_name = (
            str(item.get("display_name") or "").strip()
            or _source_display_name(source)
        )
        pairs.append((source, display_name))

    return pairs


def _follow_up_context_from_turn(
    turn: ConversationTurnRecord,
) -> ConversationFollowUpContext | None:
    artifacts = turn.artifacts
    if _artifacts_workspace_scope(artifacts) != "global":
        return None

    reason = str(artifacts.get("reason") or "").strip().lower()
    compare_sources = _compare_sources_from_artifacts(artifacts)
    compare_field = str(artifacts.get("compare_field") or "").strip() or None
    if reason == "compare_result" and len(compare_sources) == 2:
        return ConversationFollowUpContext(
            kind="compare",
            compare_sources=tuple(source for source, _display_name in compare_sources),
            compare_display_names=tuple(
                display_name for _source, display_name in compare_sources
            ),
            compare_field=compare_field,
            anchor_query=turn.query,
        )

    selected_source = str(artifacts.get("selected_source") or "").strip()
    if not selected_source:
        return None

    return ConversationFollowUpContext(
        kind="single_document",
        source=selected_source,
        source_display_name=(
            str(artifacts.get("selected_source_display_name") or "").strip()
            or _source_display_name(selected_source)
        ),
        anchor_query=turn.query,
    )


def _turn_blocks_follow_up_context(turn: ConversationTurnRecord) -> bool:
    if _artifacts_workspace_scope(turn.artifacts) == "document":
        return True

    reason = str(turn.artifacts.get("reason") or "").strip().lower()
    return reason in {"reset", "multiple_documents_match", "compare_documents_needed", "compare_picker"}


def _turn_ends_active_follow_up_context(turn: ConversationTurnRecord) -> bool:
    if not turn.query.strip():
        return False
    return True


def _resolve_follow_up_context(
    turns: list[ConversationTurnRecord],
) -> ConversationFollowUpContext | None:
    for turn in reversed(turns):
        context = _follow_up_context_from_turn(turn)
        if context is not None:
            return context
        if _turn_blocks_follow_up_context(turn):
            return None
        if _turn_ends_active_follow_up_context(turn):
            return None
    return None


def _query_mentions_any_retrieved_document(
    query: str,
    results: list[tuple[Any, float]],
) -> bool:
    return any(_query_mentions_document(query, doc) for doc, _score in results)


def _merge_scope_artifacts(
    artifacts: dict[str, Any],
    *,
    selected_source: str | None,
    workspace_scope: str,
) -> dict[str, Any]:
    merged = dict(artifacts)
    if selected_source:
        merged["selected_source"] = selected_source
        merged["selected_source_display_name"] = _source_display_name(selected_source)
        merged["workspace_scope"] = (
            "document" if workspace_scope == "document" else "global"
        )
    return merged


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
        _normalize_source_match_text(str(doc.metadata.get("subject") or "")),
        _normalize_source_match_text(str(doc.metadata.get("company") or "")),
    ):
        if not candidate:
            continue
        if candidate not in terms:
            terms.append(candidate)
        without_trailing_numbers = re.sub(r"(?:\s+\d+)+$", "", candidate).strip()
        if without_trailing_numbers and without_trailing_numbers not in terms:
            terms.append(without_trailing_numbers)
    return terms


def _unique_source_docs(results: list[tuple[Any, float]]) -> dict[str, Any]:
    docs_by_source: dict[str, Any] = {}
    for doc, _score in results:
        source = str(doc.metadata.get("source") or "")
        if source and source not in docs_by_source:
            docs_by_source[source] = doc
    return docs_by_source


def _docs_by_source(results: list[tuple[Any, float]]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    seen_keys: set[tuple[str, Any, str]] = set()
    for doc, _score in results:
        source = str(doc.metadata.get("source") or "")
        if not source:
            continue
        key = (
            source,
            doc.metadata.get("page"),
            (doc.page_content or "").strip(),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        grouped.setdefault(source, []).append(doc)
    return grouped


def _document_match_aliases(doc: Any) -> list[str]:
    aliases: set[str] = set()
    for term in _document_query_terms(doc):
        if not term:
            continue

        aliases.add(term)
        for brand_phrase, brand_aliases in TRUSTED_BRAND_ALIASES.items():
            if brand_phrase in term:
                aliases.update(brand_aliases)

        tokens = [token for token in term.split() if token and not token.isdigit()]
        meaningful_tokens = [
            token
            for token in tokens
            if len(token) >= 3 and token not in DOCUMENT_ALIAS_STOPWORDS
        ]

        for token in meaningful_tokens:
            aliases.add(token)

        for index in range(len(meaningful_tokens) - 1):
            left = meaningful_tokens[index]
            right = meaningful_tokens[index + 1]
            aliases.add(f"{left} {right}")
            if len(left) >= 2 and len(right) >= 2:
                aliases.add(f"{left[:2]}{right[:2]}")

        initials = "".join(token[0] for token in meaningful_tokens[:4])
        if 2 <= len(initials) <= 6:
            aliases.add(initials)

    return sorted(
        {alias.strip() for alias in aliases if alias.strip()},
        key=lambda alias: (-len(alias.replace(" ", "")), alias),
    )


def _trusted_brand_aliases_from_docs(docs: list[Any]) -> set[str]:
    alias_matches: set[str] = set()
    if not docs:
        return alias_matches

    combined_terms = " ".join(
        term
        for doc in docs
        for term in _document_query_terms(doc)
    )

    for brand_phrase, brand_aliases in TRUSTED_BRAND_ALIASES.items():
        if brand_phrase in combined_terms:
            alias_matches.update(brand_aliases)

    return alias_matches


def _source_match_aliases(docs: list[Any]) -> list[str]:
    aliases: set[str] = set()
    for doc in docs:
        aliases.update(_document_match_aliases(doc))

    aliases.update(_trusted_brand_aliases_from_docs(docs))

    return sorted(
        {alias.strip() for alias in aliases if alias.strip()},
        key=lambda alias: (-len(alias.replace(" ", "")), alias),
    )


def _alias_match_position(normalized_query: str, alias: str) -> int | None:
    tokens = [token for token in alias.split() if token]
    if not tokens:
        return None
    pattern = r"\b" + r"\s+".join(re.escape(token) for token in tokens) + r"\b"
    match = re.search(pattern, normalized_query, re.I)
    if not match:
        return None
    return match.start()


def _resolve_compare_sources(
    query: str,
    results: list[tuple[Any, float]],
) -> list[tuple[str, Any]]:
    normalized_query = _normalize_source_match_text(query)
    matches: list[tuple[int, int, str, Any]] = []
    grouped_docs = _docs_by_source(results)
    first_docs = _unique_source_docs(results)

    for source, docs in grouped_docs.items():
        doc = first_docs.get(source)
        if doc is None:
            continue
        best_match_score = 0
        best_match_position: int | None = None
        for alias in _source_match_aliases(docs):
            compact_alias = alias.replace(" ", "")
            if len(compact_alias) < 4:
                continue
            match_position = _alias_match_position(normalized_query, alias)
            if match_position is None:
                continue

            alias_score = len(compact_alias)
            if " " in alias:
                alias_score += 2
            if (
                best_match_position is None
                or match_position < best_match_position
                or (
                    match_position == best_match_position
                    and alias_score > best_match_score
                )
            ):
                best_match_score = alias_score
                best_match_position = match_position

        if best_match_score > 0 and best_match_position is not None:
            matches.append((best_match_position, -best_match_score, source, doc))

    matches.sort(key=lambda item: (item[0], item[1], _source_display_name(item[2]).lower()))
    return [(source, doc) for _position, _neg_score, source, doc in matches]


def _best_retrieval_score_by_source(results: list[tuple[Any, float]]) -> dict[str, float]:
    best_scores: dict[str, float] = {}
    for doc, score in results:
        source = str(doc.metadata.get("source") or "")
        if not source:
            continue
        current = best_scores.get(source)
        if current is None or score < current:
            best_scores[source] = score
    return best_scores


def _stub_doc_for_source(source: str) -> Any:
    return SimpleNamespace(
        page_content="",
        metadata={
            "source": source,
            "title": _source_display_name(source),
        },
    )


def _compare_confidence_rank(confidence: str) -> int:
    if confidence == "high":
        return 0
    if confidence == "medium":
        return 1
    return 2


def _build_compare_resolution(
    query: str,
    results: list[tuple[Any, float]],
    *,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    normalized_query = _normalize_source_match_text(query)
    grouped_docs = _docs_by_source(results)
    first_docs = _unique_source_docs(results)
    if tenant_id:
        for source in _tenant_document_sources(tenant_id):
            if source not in grouped_docs:
                grouped_docs[source] = [_stub_doc_for_source(source)]
            if source not in first_docs:
                first_docs[source] = grouped_docs[source][0]
    best_scores = _best_retrieval_score_by_source(results)
    grouped_matches: dict[int, list[dict[str, Any]]] = {}
    unmatched_candidates: list[dict[str, Any]] = []

    for source, docs in grouped_docs.items():
        doc = first_docs.get(source)
        if doc is None:
            continue

        best_alias = ""
        best_alias_score = 0
        best_match_position: int | None = None
        for alias in _source_match_aliases(docs):
            compact_alias = alias.replace(" ", "")
            if len(compact_alias) < 4:
                continue
            match_position = _alias_match_position(normalized_query, alias)
            if match_position is None:
                continue

            alias_score = len(compact_alias)
            if " " in alias:
                alias_score += 2
            if any(alias in aliases for aliases in TRUSTED_BRAND_ALIASES.values()):
                alias_score += 1
            if (
                best_match_position is None
                or match_position < best_match_position
                or (
                    match_position == best_match_position
                    and alias_score > best_alias_score
                )
            ):
                best_alias = alias
                best_alias_score = alias_score
                best_match_position = match_position

        candidate = {
            "source": source,
            "doc": doc,
            "display_name": _source_display_name(source),
            "retrieval_score": float(best_scores.get(source, 99.0)),
            "matched_alias": best_alias or None,
            "alias_score": best_alias_score,
            "match_position": best_match_position,
            "confidence": "low",
        }
        if best_match_position is None:
            unmatched_candidates.append(candidate)
        else:
            grouped_matches.setdefault(best_match_position, []).append(candidate)

    confident_sources: list[dict[str, Any]] = []
    ordered_candidates: list[dict[str, Any]] = []

    for position in sorted(grouped_matches):
        candidates = sorted(
            grouped_matches[position],
            key=lambda item: (
                -int(item["alias_score"]),
                float(item["retrieval_score"]),
                str(item["display_name"]).lower(),
            ),
        )
        top = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        top_score = int(top["alias_score"])
        runner_score = int(runner_up["alias_score"]) if runner_up else -1
        retrieval_margin = (
            float(runner_up["retrieval_score"]) - float(top["retrieval_score"])
            if runner_up
            else None
        )

        confidence = "medium"
        if top_score >= 4 and (
            runner_up is None
            or top_score - runner_score >= 3
            or (
                top_score > runner_score
                and retrieval_margin is not None
                and retrieval_margin >= 0.12
            )
        ):
            confidence = "high"
        elif top_score < 4:
            confidence = "low"

        top["confidence"] = confidence
        ordered_candidates.append(top)
        if confidence == "high":
            confident_sources.append(top)
        for candidate in candidates[1:]:
            candidate["confidence"] = "low"
            ordered_candidates.append(candidate)

    ordered_candidates.extend(
        sorted(
            unmatched_candidates,
            key=lambda item: (
                float(item["retrieval_score"]),
                str(item["display_name"]).lower(),
            ),
        )
    )

    picker_candidates: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    for candidate in sorted(
        ordered_candidates,
        key=lambda item: (
            _compare_confidence_rank(str(item["confidence"])),
            int(item["match_position"]) if item["match_position"] is not None else 10**9,
            float(item["retrieval_score"]),
            -int(item["alias_score"]),
            str(item["display_name"]).lower(),
        ),
    ):
        source = str(candidate["source"])
        if not source or source in seen_sources:
            continue
        seen_sources.add(source)
        picker_candidates.append(
            {
                "source": source,
                "display_name": str(candidate["display_name"]),
                "confidence": str(candidate["confidence"]),
                "matched_alias": candidate["matched_alias"],
                "retrieval_score": round(float(candidate["retrieval_score"]), 4),
            }
        )

    auto_sources: list[tuple[str, Any]] = []
    if len(confident_sources) >= 2:
        for candidate in confident_sources[:2]:
            auto_sources.append((str(candidate["source"]), candidate["doc"]))

    picker_selection: list[dict[str, Any]] = []
    if len(confident_sources) == 1:
        picker_selection.append(confident_sources[0])
    else:
        if confident_sources:
            picker_selection.append(confident_sources[0])

        for candidate in picker_candidates:
            if any(
                str(existing["source"]) == str(candidate["source"])
                for existing in picker_selection
            ):
                continue
            matching_candidate = next(
                (
                    item
                    for item in ordered_candidates
                    if str(item["source"]) == str(candidate["source"])
                ),
                None,
            )
            if matching_candidate is not None:
                picker_selection.append(matching_candidate)
            if len(picker_selection) >= 2:
                break

    left_candidate = picker_selection[0] if picker_selection else None
    right_candidate = picker_selection[1] if len(picker_selection) > 1 else None

    return {
        "auto_sources": auto_sources,
        "confident_sources": [
            {
                "source": str(candidate["source"]),
                "display_name": str(candidate["display_name"]),
                "confidence": str(candidate["confidence"]),
                "matched_alias": candidate.get("matched_alias"),
            }
            for candidate in confident_sources
        ],
        "picker_candidates": picker_candidates[:8],
        "picker_left": {
            "source": str(left_candidate["source"]),
            "display_name": str(left_candidate["display_name"]),
            "confidence": str(left_candidate["confidence"]),
            "matched_alias": left_candidate.get("matched_alias"),
        }
        if left_candidate
        else None,
        "picker_right": {
            "source": str(right_candidate["source"]),
            "display_name": str(right_candidate["display_name"]),
            "confidence": str(right_candidate["confidence"]),
            "matched_alias": right_candidate.get("matched_alias"),
        }
        if right_candidate
        else None,
        "resolved_sources": [
            {
                "source": str(candidate["source"]),
                "display_name": str(candidate["display_name"]),
                "confidence": str(candidate["confidence"]),
                "matched_alias": candidate.get("matched_alias"),
            }
            for candidate in confident_sources[:2]
        ],
    }


def _compare_debug_source_identity(
    *,
    source: str,
    title: str | None = None,
    retrieval_score: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "source": source,
        "display_name": _source_display_name(source),
        "normalized_source_id": _normalize_source_match_text(
            _source_display_name(source)
        ),
    }
    if title:
        payload["title"] = title
        payload["normalized_title"] = _normalize_source_match_text(title)
    if retrieval_score is not None:
        payload["retrieval_score"] = round(float(retrieval_score), 4)
    return payload


def _serialize_compare_resolution_debug(
    resolution: dict[str, Any],
) -> dict[str, Any]:
    return {
        "confident_sources": list(resolution.get("confident_sources") or []),
        "auto_sources": [
            _compare_debug_source_identity(
                source=str(source),
                title=str(getattr(doc, "metadata", {}).get("title") or "").strip() or None,
            )
            for source, doc in list(resolution.get("auto_sources") or [])
        ],
        "picker_left": resolution.get("picker_left"),
        "picker_right": resolution.get("picker_right"),
        "picker_candidates": list(resolution.get("picker_candidates") or []),
    }


def _compare_retrieval_hit_debug(results: list[tuple[Any, float]]) -> list[dict[str, Any]]:
    seen_sources: set[str] = set()
    debug_hits: list[dict[str, Any]] = []
    for doc, score in results:
        source = str(doc.metadata.get("source") or "").strip()
        if not source or source in seen_sources:
            continue
        seen_sources.add(source)
        debug_hits.append(
            _compare_debug_source_identity(
                source=source,
                title=str(doc.metadata.get("title") or "").strip() or None,
                retrieval_score=score,
            )
        )
    return debug_hits


def _strip_document_references_from_query(query: str, docs: list[Any]) -> str:
    stripped = query
    for doc in docs:
        for alias in _source_match_aliases([doc]):
            if len(alias.replace(" ", "")) < 4:
                continue
            pattern = r"\b" + r"[\s\-_]+".join(re.escape(token) for token in alias.split()) + r"\b"
            stripped = re.sub(pattern, "", stripped, flags=re.I)

    stripped = re.sub(r"\s+", " ", stripped)
    stripped = re.sub(r"\s+([?.!,;:])", r"\1", stripped).strip()
    return stripped or query


def _strip_source_references_from_query(
    query: str,
    sources: list[str],
    results: list[tuple[Any, float]],
) -> str:
    stripped = query
    grouped_docs = _docs_by_source(results)
    for source in sources:
        for alias in _source_match_aliases(grouped_docs.get(source, [])):
            if len(alias.replace(" ", "")) < 4:
                continue
            pattern = r"\b" + r"[\s\-_]+".join(re.escape(token) for token in alias.split()) + r"\b"
            stripped = re.sub(pattern, "", stripped, flags=re.I)

    stripped = re.sub(r"\s+", " ", stripped)
    stripped = re.sub(r"\s+([?.!,;:])", r"\1", stripped).strip()
    return stripped or query


def _clean_compare_focus_query(query: str) -> str:
    cleaned = query.strip()
    cleaned = re.sub(r"^\s*compare\b", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:vs|versus)\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bbetween\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\b(?:these|those|the|both|each|two|2)\s+(?:cards?|documents?|docs?|agreements?|files?)\b",
        " ",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"\band\b", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b(?:for|of|and|between)\b(?=\s*(?:[?.!,;:]|$))", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .,:;?")


def _normalize_compare_focus_query(query: str) -> str:
    cleaned = _clean_compare_focus_query(query)
    cleaned = re.sub(
        r"^\s*(?:and|also|so|then)\b[\s,:-]*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"^\s*(?:what about|how about|tell me about|show me|give me)\b[\s,:-]*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(
        r"^\s*what(?:'s|\s+is|\s+are)\b[\s,:-]*",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"^\s*(?:the|any)\b\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" .,:;?") or query.strip()


def _compare_focus_query_from_sources(
    *,
    query: str,
    sources: list[str],
    requested_focus_query: str | None = None,
) -> str:
    requested = str(requested_focus_query or "").strip()
    if requested:
        return _normalize_compare_focus_query(requested)

    if sources:
        stripped_query = _strip_document_references_from_query(
            query,
            [_stub_doc_for_source(source) for source in sources],
        )
        return _normalize_compare_focus_query(stripped_query)

    return _normalize_compare_focus_query(query)


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


def _is_explicit_compare_query(query: str) -> bool:
    return bool(
        re.search(r"\bcompare\b|\bcomparison\b|\bvs\.?\b|\bversus\b", query, re.I)
        or (
            re.search(r"\b(?:both|each)\b", query, re.I)
            and re.search(r"\b(?:cards?|documents?|docs?|agreements?|files?)\b", query, re.I)
        )
        or (
            re.search(r"\bbetween\b", query, re.I)
            and re.search(r"\b(?:two|2|both|these|those)\b", query, re.I)
        )
    )


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
        r"^compare (.+)$",
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


def _build_compare_answer(compare_results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in compare_results:
        value = item["value"] if item.get("found") else "Not explicitly found"
        lines.append(f"{item['display_name']} -> {value}")
    return "\n".join(lines)


def _canonical_compare_field(compare_query: str) -> tuple[str, str, list[str]]:
    focus_phrase = _extract_focus_phrase(compare_query) or compare_query.strip().lower()
    normalized_focus = _normalize_for_match(focus_phrase)

    if normalized_focus in {
        "apr",
        "annual percentage rate",
        "purchase apr",
        "purchase annual percentage rate",
        "variable apr",
        "balance transfer apr",
        "balance transfer annual percentage rate",
        "cash advance apr",
        "cash advance annual percentage rate",
    }:
        return (
            "apr",
            "APR",
            [
                "purchase apr",
                "purchase annual percentage rate",
                "variable apr",
                "annual percentage rate",
                "apr",
                "balance transfer apr",
                "balance transfer annual percentage rate",
                "cash advance apr",
                "cash advance annual percentage rate",
            ],
        )

    if normalized_focus in {"annual fee", "annual membership fee"}:
        return ("annual_fee", "annual fee", ["annual fee", "annual membership fee"])

    if normalized_focus in {"late fee", "late payment fee", "late payment"}:
        return ("late_fee", "late fee", ["late payment fee", "late fee", "late payment"])

    if normalized_focus in {"foreign transaction fee", "foreign transaction"}:
        return (
            "foreign_transaction_fee",
            "foreign transaction fee",
            ["foreign transaction fee", "foreign transaction"],
        )

    return (
        normalized_focus or focus_phrase,
        focus_phrase.strip(" .,:;?") or compare_query.strip() or "that field",
        _focus_phrase_variants(focus_phrase) or ([focus_phrase] if focus_phrase else []),
    )


def _normalize_percent_range(value: str) -> str | None:
    range_match = re.search(
        r"(\d+(?:\.\d+)?%)\s*(?:to|-|–|—)\s*(\d+(?:\.\d+)?%)",
        value,
        re.I,
    )
    if range_match:
        return f"{range_match.group(1)}–{range_match.group(2)}"

    single_match = re.search(r"(\d+(?:\.\d+)?%)", value, re.I)
    if single_match:
        return single_match.group(1)

    return None


def _normalize_compare_field_value(field_key: str, raw_value: str | None) -> str | None:
    compact = re.sub(r"\s+", " ", str(raw_value or "")).strip()
    if not compact:
        return None

    normalized_none = re.sub(r"[^a-z]+", "", compact.lower())
    if normalized_none in {"none", "nonefirsttimeyoupaylate"} or compact.lower() in {"no ne", "none."}:
        if field_key == "annual_fee":
            return "No annual fee."
        if field_key == "foreign_transaction_fee":
            return "No foreign transaction fee."
        if field_key == "late_fee":
            return "No late fee."
        return "None."

    if field_key == "apr":
        normalized_apr = _normalize_percent_range(compact)
        if normalized_apr:
            return f"Variable APR: {normalized_apr}."

    if field_key == "annual_fee":
        amount_match = re.search(r"\$\s*\d[\d,]*(?:\.\d+)?", compact)
        if amount_match:
            return f"{amount_match.group(0)}."

    if field_key == "late_fee":
        up_to_match = re.search(r"up to\s+(\$\s*\d[\d,]*(?:\.\d+)?)", compact, re.I)
        if up_to_match and re.search(r"\bnone\b.*\bfirst time\b", compact, re.I):
            return f"None first time, then up to {up_to_match.group(1)}."
        if up_to_match:
            return f"Up to {up_to_match.group(1)}."
        amount_match = re.search(r"\$\s*\d[\d,]*(?:\.\d+)?", compact)
        if amount_match:
            return f"Up to {amount_match.group(0)}."

    if field_key == "foreign_transaction_fee":
        if re.fullmatch(r"\$\s*0+(?:\.0+)?\.?", compact):
            return "No foreign transaction fee."
        amount_match = re.search(r"\$\s*\d[\d,]*(?:\.\d+)?", compact)
        if amount_match:
            return f"{amount_match.group(0)}."
        percent_match = _normalize_percent_range(compact)
        if percent_match:
            return f"{percent_match}."

    compact_sentence = _compact_field_answer_value(compact)
    if compact_sentence.lower() == "none":
        if field_key == "annual_fee":
            return "No annual fee."
        if field_key == "foreign_transaction_fee":
            return "No foreign transaction fee."
        if field_key == "late_fee":
            return "No late fee."
        return "None."

    if compact_sentence and compact_sentence[-1] not in ".!?":
        compact_sentence = f"{compact_sentence}."
    return compact_sentence or None


def _extract_canonical_compare_field_value(
    text: str,
    *,
    field_key: str,
    field_aliases: list[str],
) -> str | None:
    normalized_text = re.sub(r"\s+", " ", text or " ")

    if field_key == "apr":
        for pattern in (
            r"annual percentage rate\s*\(apr\)\s*for purchases\s*(?:from)?\s*([0-9.]+%\s*(?:to|-|–|—)\s*[0-9.]+%|[0-9.]+%)",
            r"purchase apr\s*(?:is|:|for)?\s*([0-9.]+%\s*(?:to|-|–|—)\s*[0-9.]+%|[0-9.]+%)",
            r"variable apr\s*(?:is|:)?\s*([0-9.]+%\s*(?:to|-|–|—)\s*[0-9.]+%|[0-9.]+%)",
        ):
            match = re.search(pattern, normalized_text, re.I)
            if match:
                return _normalize_compare_field_value(field_key, match.group(1))

    if field_key == "annual_fee":
        match = re.search(
            r"(?:^|\n)\s*annual fee(?!\s+for)\s*:?\s*(none\b|no\s*ne\b|\$\s*\d[\d,]*(?:\.\d+)?)",
            text,
            re.I,
        )
        if match:
            return _normalize_compare_field_value(field_key, match.group(1))

    if field_key == "foreign_transaction_fee":
        match = re.search(
            r"(?:^|\n)\s*foreign transaction(?: fee)?\s*:?\s*(none\b|no\s*ne\b|\$\s*\d[\d,]*(?:\.\d+)?|\d+(?:\.\d+)?%)",
            text,
            re.I,
        )
        if match:
            return _normalize_compare_field_value(field_key, match.group(1))

    if field_key == "late_fee":
        match = re.search(
            r"(?:^|\n)\s*late fee\s*:?\s*([^\n]{1,160})",
            text,
            re.I,
        )
        if match:
            normalized = _normalize_compare_field_value(field_key, match.group(1))
            if normalized:
                return normalized

    for alias in field_aliases:
        extracted = _extract_field_value(text, alias)
        normalized = _normalize_compare_field_value(field_key, extracted)
        if normalized:
            return normalized

    return None


def _compare_result_for_source(
    *,
    tenant_id: str,
    source: str,
    compare_query: str,
) -> tuple[dict[str, Any], list[tuple[Any, float]]]:
    raw_results, _status = retrieve(
        compare_query,
        k=8,
        tenant_id=tenant_id,
        return_status=True,
        source_filter=source,
    )
    results = _rerank_results(compare_query, dedupe_results(raw_results))
    field_key, _field_label, field_aliases = _canonical_compare_field(compare_query)

    field_value = None
    field_result = None
    for doc, score in results:
        extracted = _extract_canonical_compare_field_value(
            doc.page_content or "",
            field_key=field_key,
            field_aliases=field_aliases,
        )
        if extracted:
            field_value = extracted
            field_result = (doc, score)
            break

    in_distance_results = [(doc, score) for doc, score in results if score <= MAX_DISTANCE]
    strong_evidence_results = [
        (doc, score)
        for doc, score in in_distance_results
        if _has_strong_answer_evidence(compare_query, doc.page_content or "")
    ]
    evidence_results = ([field_result] if field_result else strong_evidence_results or in_distance_results or results)[:1]

    return (
        {
            "source": source,
            "display_name": _source_display_name(source),
            "value": field_value,
            "found": bool(field_value),
        },
        evidence_results,
    )


def _select_best_field_value_result(
    query: str,
    results: list[tuple[Any, float]],
) -> tuple[str | None, tuple[Any, float] | None]:
    focus_phrase = _extract_focus_phrase(query) or query.strip().lower() or None
    best_value: str | None = None
    best_result: tuple[Any, float] | None = None
    best_rank: tuple[int, float, int] | None = None

    for index, (doc, score) in enumerate(results):
        field_value = _extract_field_value(doc.page_content or "", focus_phrase)
        if not field_value:
            continue

        page = doc.metadata.get("page")
        page_rank = int(page) if isinstance(page, int) else 9999
        rank = (page_rank, score, index)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best_value = field_value
            best_result = (doc, score)

    return best_value, best_result


def _scan_source_document_for_field_value(
    *,
    source: str,
    query: str,
) -> tuple[str | None, tuple[Any, float] | None]:
    source_path = str(source or "").strip()
    if not source_path or not os.path.isfile(source_path):
        return None, None

    if not source_path.lower().endswith(".pdf"):
        return None, None

    try:
        from pypdf import PdfReader
    except Exception:
        return None, None

    focus_phrase = _extract_focus_phrase(query) or query.strip().lower() or None

    try:
        reader = PdfReader(source_path)
    except Exception:
        return None, None

    for page_index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if not text.strip():
            continue

        field_value = _extract_field_value(text, focus_phrase)
        if not field_value:
            continue

        return (
            field_value,
            (
                SimpleNamespace(
                    page_content=text,
                    metadata={"source": source_path, "page": page_index},
                ),
                0.0,
            ),
        )

    return None, None


def _document_workspace_compare_focus_query(query: str) -> str:
    cleaned = _clean_compare_focus_query(query)
    cleaned = re.sub(r"\b(?:vs|versus)\b.+$", "", cleaned, flags=re.I).strip()
    cleaned = re.split(
        r"\b(?:for|between)\b",
        cleaned,
        maxsplit=1,
        flags=re.I,
    )[0].strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;?")
    return cleaned or query.strip()


def _build_document_workspace_compare_answer(
    *,
    source: str,
    compare_focus_query: str,
    field_value: str | None,
) -> str:
    display_name = _source_display_name(source)
    readable_name = re.sub(r"\.[a-z0-9]+$", "", display_name, flags=re.I)
    readable_name = re.sub(r"[-_]+", " ", readable_name)
    readable_name = re.sub(r"\s+", " ", readable_name).strip()
    if "american express" in readable_name.lower():
        subject_label = "Amex"
    elif "discover" in readable_name.lower():
        subject_label = "Discover"
    elif "prime" in readable_name.lower():
        subject_label = "Prime"
    else:
        subject_label = readable_name.title() if readable_name else "This document"

    focus_label = _extract_focus_phrase(compare_focus_query) or compare_focus_query.strip()
    focus_label = focus_label.strip(" .,:;?") or "that field"

    if field_value:
        return (
            f"{subject_label} {focus_label} is {field_value}.\n\n"
            "Cross-document comparison is not available in Document Workspace. "
            "Switch to Global Chat to compare documents."
        )

    return (
        f"Cross-document comparison is not available in Document Workspace. "
        f"I couldn't find a direct answer for {focus_label} in {subject_label}. "
        "Switch to Global Chat to compare documents."
    )


def _compare_subject_label(source: str) -> str:
    display_name = _source_display_name(source)
    readable_name = re.sub(r"\.[a-z0-9]+$", "", display_name, flags=re.I)
    readable_name = re.sub(r"[-_]+", " ", readable_name)
    readable_name = re.sub(r"\s+", " ", readable_name).strip()
    lowered = readable_name.lower()
    if "american express" in lowered or "amex" in lowered:
        return "Amex"
    if "discover" in lowered:
        return "Discover"
    if "prime" in lowered:
        return "Prime"
    if "citibank" in lowered or "citi" in lowered:
        return "Citi"
    return readable_name.title() if readable_name else "This document"


def _build_single_source_compare_answer(
    *,
    source: str,
    compare_focus_query: str,
    field_value: str,
) -> str:
    subject_label = _compare_subject_label(source)
    focus_label = _extract_focus_phrase(compare_focus_query) or compare_focus_query.strip().lower()
    focus_label = focus_label.strip(" .,:;?")
    compact_value = _compact_field_answer_value(field_value)

    if not compact_value or not focus_label:
        return field_value

    if compact_value == "none":
        return f"{subject_label} has no {focus_label}."

    return f"{subject_label} {focus_label} is {compact_value}."


def _compact_field_answer_value(value: str) -> str:
    compact = re.sub(r"\s+", " ", str(value or "")).strip()
    if not compact:
        return ""

    sentence_match = re.match(r"(.+?[.!?])(?:\s|$)", compact)
    if sentence_match:
        compact = sentence_match.group(1).strip()

    compact = compact.rstrip(".!?").strip()
    if not compact:
        return ""

    if compact.lower() in {"none", "no ne"}:
        return "none"

    if compact[:1].isalpha():
        compact = compact[:1].lower() + compact[1:]

    return compact


def _build_bounded_field_direct_answer(
    *,
    query: str,
    field_value: str,
) -> str:
    focus_label = _extract_focus_phrase(query) or query.strip().lower()
    focus_label = focus_label.strip(" .,:;?")
    focus_label = re.sub(r"^(?:the|a|an)\s+", "", focus_label, flags=re.I)

    compact_value = _compact_field_answer_value(field_value)
    if not compact_value or not focus_label:
        return field_value

    if compact_value == "none":
        return f"There is no {focus_label}."

    return f"The {focus_label} is {compact_value}."


# =====================================================
# Main Query Endpoint
# =====================================================
@app.post("/query")
def query_docs(payload: QueryRequest, request: Request):
    original_query = payload.query
    tenant_id = request.state.tenant_id
    conversation_id = payload.conversation_id
    selected_source = str(payload.selected_source or "").strip()
    client_selected_source = selected_source
    workspace_scope = str(payload.workspace_scope or "global").strip().lower() or "global"
    if workspace_scope not in {"global", "document"}:
        workspace_scope = "global"

    is_document_workspace = workspace_scope == "document"
    explicit_compare_query = _is_explicit_compare_query(original_query)
    follow_up_context_enabled = payload.follow_up_context is not False
    compare_follow_up_enabled = payload.compare_follow_up is not False
    requested_compare_sources = _sanitize_compare_sources(
        tenant_id,
        payload.compare_sources,
    )
    requested_compare_focus_query = str(payload.compare_focus_query or "").strip() or None
    conversation_turns = (
        get_recent_conversation_turns(tenant_id, conversation_id)
        if conversation_id
        else []
    )
    inferred_follow_up_context: ConversationFollowUpContext | None = None
    inferred_compare_sources: list[tuple[str, str]] = []
    compare_context_cleared = False

    if is_document_workspace and not selected_source:
        raise HTTPException(
            status_code=400,
            detail="Document workspace queries require a selected source.",
        )

    def scoped_artifacts(base_artifacts: dict[str, Any]) -> dict[str, Any]:
        return _merge_scope_artifacts(
            base_artifacts,
            selected_source=selected_source or None,
            workspace_scope=workspace_scope,
        )

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
                artifacts=scoped_artifacts({"reason": "reset"}),
                debug={"reset": True} if payload.debug else None,
            )
        )

    # ---------------- conversation follow-up context ----------------
    if (
        follow_up_context_enabled
        and not is_document_workspace
        and not selected_source
        and not explicit_compare_query
    ):
        candidate_context = _resolve_follow_up_context(conversation_turns)
        if candidate_context is not None:
            if candidate_context.kind == "compare" and not compare_follow_up_enabled:
                compare_context_cleared = True
            else:
                preflight_results, _preflight_status = retrieve(
                    original_query,
                    k=15,
                    tenant_id=tenant_id,
                    return_status=True,
                )
                preflight_distance_results = dedupe_results(preflight_results)
                if not _query_mentions_any_retrieved_document(
                    original_query,
                    preflight_distance_results,
                ):
                    inferred_follow_up_context = candidate_context
                    if candidate_context.kind == "single_document" and candidate_context.source:
                        selected_source = candidate_context.source
                    elif candidate_context.kind == "compare":
                        inferred_compare_sources = list(
                            zip(
                                candidate_context.compare_sources,
                                candidate_context.compare_display_names,
                            )
                        )

    # ---------------- rewrite (history-backed fallback) ----------------
    last_successful_query = (
        _last_successful_query_from_turns(conversation_turns)
        if follow_up_context_enabled
        else None
    )

    rewritten_query = original_query
    if (
        inferred_follow_up_context is None
        and not compare_context_cleared
        and not selected_source
        and len(original_query.split()) <= 6
        and last_successful_query
    ):
        rewritten_query = f"In the context of {last_successful_query}, {original_query}"

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
                artifacts=scoped_artifacts({"reason": "vague_query"}),
                debug={"reason": "vague_query"} if payload.debug else None,
            )
        )

    if mentions_external_entity(original_query) and not explicit_compare_query:
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer=refusal_message("external_entity"),
                citations=[],
                artifacts=scoped_artifacts({"reason": "external_entity"}),
                debug={"reason": "external_entity"} if payload.debug else None,
            )
        )

    # ---------------- retrieval ----------------
    if explicit_compare_query and is_document_workspace:
        compare_focus_query = _document_workspace_compare_focus_query(original_query)
        _document_compare_field_key, document_compare_field_label, _document_compare_aliases = _canonical_compare_field(compare_focus_query)
        retrieval_query = compare_focus_query or original_query
        raw_results, status = retrieve(
            retrieval_query,
            k=15,
            tenant_id=tenant_id,
            return_status=True,
            source_filter=selected_source,
        )
        raw_distance_results = dedupe_results(raw_results)

        if status == "no_documents_ingested":
            return persist_and_return(
                wrap_response(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    query=original_query,
                    mode="hard_refusal",
                    answer="There are no documents available yet to answer this question.",
                    citations=[],
                    artifacts=scoped_artifacts({"reason": "no_documents_ingested"}),
                    debug={"status": status} if payload.debug else None,
                )
            )

        compare_results = _rerank_results(compare_focus_query, raw_distance_results)
        selected_field_value, selected_field_result = _select_best_field_value_result(
            compare_focus_query,
            compare_results,
        )
        if selected_field_value is None:
            selected_field_value, selected_field_result = _scan_source_document_for_field_value(
                source=selected_source,
                query=compare_focus_query,
            )
        in_distance_results = [
            (doc, score)
            for doc, score in compare_results
            if score <= MAX_DISTANCE
        ]
        strong_evidence_results = [
            (doc, score)
            for doc, score in in_distance_results
            if _has_strong_answer_evidence(compare_focus_query, doc.page_content or "")
        ]
        if selected_field_result is not None:
            strong_evidence_results = [selected_field_result]
        evidence_results = (strong_evidence_results or in_distance_results or compare_results)[:3]
        citations = build_citations(evidence_results, compare_focus_query) if evidence_results else []

        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="guided_fallback",
                answer=_build_document_workspace_compare_answer(
                    source=selected_source,
                    compare_focus_query=compare_focus_query,
                    field_value=selected_field_value,
                ),
                citations=citations,
                artifacts=scoped_artifacts(
                    {
                        "reason": "document_workspace_compare_requires_global_chat",
                        "compare_field": document_compare_field_label,
                    }
                ),
                debug={
                    "rewritten_query": rewritten_query,
                    "compare_focus_query": compare_focus_query,
                    "results_count": len(compare_results),
                    "selected_document_answer_found": bool(selected_field_value),
                }
                if payload.debug
                else None,
            )
        )

    if (explicit_compare_query or inferred_compare_sources) and not is_document_workspace:
        compare_sources: list[tuple[str, Any]] = []
        compare_focus_query = original_query
        _compare_field_key, compare_focus_phrase, _compare_field_aliases = _canonical_compare_field(compare_focus_query)
        compare_resolution_debug: dict[str, Any] = {
            "rewritten_query": rewritten_query,
            "follow_up_context_kind": (
                inferred_follow_up_context.kind if inferred_follow_up_context else None
            ),
        }

        if requested_compare_sources:
            compare_sources = [
                (
                    source,
                    SimpleNamespace(
                        metadata={
                            "source": source,
                            "title": _source_display_name(source),
                        }
                    ),
                )
                for source in requested_compare_sources
            ]
            compare_focus_query = _compare_focus_query_from_sources(
                query=original_query,
                sources=requested_compare_sources,
                requested_focus_query=requested_compare_focus_query,
            )
            _compare_field_key, compare_focus_phrase, _compare_field_aliases = _canonical_compare_field(compare_focus_query)
            compare_resolution_debug["resolved_compare_sources"] = [
                _source_display_name(source)
                for source, _doc in compare_sources
            ]
            compare_resolution_debug["compare_sources_from_picker"] = True
            compare_resolution_debug["compare_focus_query_from_picker"] = bool(
                requested_compare_focus_query
            )
        elif explicit_compare_query:
            raw_results, status = retrieve(
                rewritten_query,
                k=15,
                tenant_id=tenant_id,
                return_status=True,
            )
            raw_distance_results = dedupe_results(raw_results)

            if status == "no_documents_ingested":
                return persist_and_return(
                    wrap_response(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        query=original_query,
                        mode="hard_refusal",
                        answer="There are no documents available yet to answer this question.",
                        citations=[],
                        artifacts=scoped_artifacts({"reason": "no_documents_ingested"}),
                        debug={"status": status} if payload.debug else None,
                    )
                )

            compare_resolution = _build_compare_resolution(
                original_query,
                raw_distance_results,
                tenant_id=tenant_id,
            )
            compare_sources = compare_resolution["auto_sources"]
            compare_focus_query = _normalize_compare_focus_query(
                _strip_source_references_from_query(
                    original_query,
                    [source for source, _doc in compare_sources],
                    raw_distance_results,
                )
            )
            _compare_field_key, compare_focus_phrase, _compare_field_aliases = _canonical_compare_field(compare_focus_query)
            compare_resolution_debug["resolved_compare_sources"] = [
                _source_display_name(source)
                for source, _doc in compare_sources
            ]
            compare_resolution_debug["compare_picker_candidates"] = [
                candidate["display_name"]
                for candidate in compare_resolution["picker_candidates"]
            ]
            compare_resolution_debug["confident_sources"] = [
                candidate["display_name"]
                for candidate in compare_resolution["confident_sources"]
            ]
            compare_resolution_debug["auto_sources"] = [
                _source_display_name(source)
                for source, _doc in compare_resolution["auto_sources"]
            ]
            if payload.debug:
                compare_resolution_debug["compare_resolution"] = (
                    _serialize_compare_resolution_debug(compare_resolution)
                )
                compare_resolution_debug["tenant_catalog_sources"] = [
                    _compare_debug_source_identity(source=source)
                    for source in _tenant_document_sources(tenant_id)
                ]
                compare_resolution_debug["retrieval_hit_sources"] = (
                    _compare_retrieval_hit_debug(raw_distance_results)
                )

            if len(compare_resolution["confident_sources"]) == 1 and compare_focus_phrase:
                resolved_source = str(compare_resolution["confident_sources"][0]["source"])
                single_source_compare_focus_query = _normalize_compare_focus_query(
                    _strip_source_references_from_query(
                        original_query,
                        [resolved_source],
                        raw_distance_results,
                    )
                )
                single_result, single_evidence_results = _compare_result_for_source(
                    tenant_id=tenant_id,
                    source=resolved_source,
                    compare_query=single_source_compare_focus_query,
                )
                picker_left = {
                    "source": resolved_source,
                    "display_name": _source_display_name(resolved_source),
                    "confidence": "high",
                    "matched_alias": compare_resolution["confident_sources"][0].get("matched_alias"),
                }
                picker_right = compare_resolution["picker_right"]
                compare_picker = {
                    "left": picker_left,
                    "right": picker_right,
                    "candidates": compare_resolution["picker_candidates"],
                    "can_submit": True,
                }

                if single_result.get("found") and single_result.get("value"):
                    return persist_and_return(
                        wrap_response(
                            tenant_id=tenant_id,
                            conversation_id=conversation_id,
                            query=original_query,
                            mode="direct_answer",
                            answer=_build_single_source_compare_answer(
                                source=resolved_source,
                                compare_focus_query=single_source_compare_focus_query,
                                field_value=str(single_result["value"]),
                            ),
                            citations=build_citations(
                                single_evidence_results,
                                single_source_compare_focus_query,
                            ),
                            artifacts=scoped_artifacts(
                                {
                                    "reason": "compare_picker",
                                    "compare_field": _extract_focus_phrase(single_source_compare_focus_query)
                                    or single_source_compare_focus_query,
                                    "compare_focus_query": single_source_compare_focus_query,
                                    "compare_picker": compare_picker,
                                }
                            ),
                            debug={
                                **compare_resolution_debug,
                                "compare_focus_query": single_source_compare_focus_query,
                                "single_confident_source": _source_display_name(resolved_source),
                            }
                            if payload.debug
                            else None,
                        )
                    )

            if len(compare_sources) != 2 or not compare_focus_phrase:
                ambiguity_citations = build_citations(
                    _best_result_per_source(raw_distance_results)[:3],
                    original_query,
                )
                picker_left = compare_resolution["picker_left"]
                picker_right = compare_resolution["picker_right"]
                compare_picker = {
                    "left": picker_left,
                    "right": picker_right,
                    "candidates": compare_resolution["picker_candidates"],
                    "can_submit": bool(compare_focus_phrase),
                }
                return persist_and_return(
                    wrap_response(
                        tenant_id=tenant_id,
                        conversation_id=conversation_id,
                        query=original_query,
                        mode="guided_fallback",
                        answer=(
                            "Pick the two documents to compare below."
                            if compare_focus_phrase
                            else "Pick two documents below, then ask for one field like annual fee or APR."
                        ),
                        citations=ambiguity_citations,
                        artifacts=scoped_artifacts(
                            {
                                "reason": "compare_picker",
                                "compare_field": compare_focus_phrase or None,
                                "compare_focus_query": compare_focus_query,
                                "compare_picker": compare_picker,
                            }
                        ),
                        debug={
                            **compare_resolution_debug,
                            "compare_focus_query": compare_focus_query,
                            "picker_left": (
                                picker_left["display_name"] if picker_left else None
                            ),
                            "picker_right": (
                                picker_right["display_name"] if picker_right else None
                            ),
                        }
                        if payload.debug
                        else None,
                    )
                )
        else:
            compare_sources = [
                (
                    source,
                    SimpleNamespace(
                        metadata={
                            "source": source,
                            "title": display_name,
                        }
                    ),
                )
                for source, display_name in inferred_compare_sources
            ]
            compare_focus_query = _normalize_compare_focus_query(original_query)
            _compare_field_key, compare_focus_phrase, _compare_field_aliases = _canonical_compare_field(compare_focus_query)
            compare_resolution_debug["resolved_compare_sources"] = [
                display_name for _source, display_name in inferred_compare_sources
            ]
            compare_resolution_debug["anchor_query"] = (
                inferred_follow_up_context.anchor_query
                if inferred_follow_up_context
                else None
            )

        if len(compare_sources) != 2 or not compare_focus_phrase:
            selected_picker = [
                {
                    "source": source,
                    "display_name": _source_display_name(source),
                    "confidence": "high",
                    "matched_alias": None,
                }
                for source, _doc in compare_sources[:2]
            ]
            picker_left = selected_picker[0] if selected_picker else None
            picker_right = selected_picker[1] if len(selected_picker) > 1 else None
            return persist_and_return(
                wrap_response(
                    tenant_id=tenant_id,
                    conversation_id=conversation_id,
                    query=original_query,
                    mode="guided_fallback",
                    answer=(
                        "Pick two documents to compare below."
                        if compare_focus_phrase
                        else "Pick two documents below, then ask for one field like annual fee or APR."
                    ),
                    citations=[],
                    artifacts=scoped_artifacts(
                        {
                            "reason": "compare_picker",
                            "compare_field": compare_focus_phrase or None,
                            "compare_focus_query": compare_focus_query,
                            "compare_picker": {
                                "left": picker_left,
                                "right": picker_right,
                                "candidates": selected_picker,
                                "can_submit": bool(compare_focus_phrase),
                            },
                        }
                    ),
                    debug={
                        **compare_resolution_debug,
                        "compare_focus_query": compare_focus_query,
                    }
                    if payload.debug
                    else None,
                )
            )

        compare_results: list[dict[str, Any]] = []
        compare_citations: list[dict[str, Any]] = []
        for source, _doc in compare_sources:
            compare_result, evidence_results = _compare_result_for_source(
                tenant_id=tenant_id,
                source=source,
                compare_query=compare_focus_query,
            )
            compare_results.append(compare_result)
            compare_citations.extend(build_citations(evidence_results, compare_focus_query))

        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="direct_answer",
                answer=_build_compare_answer(compare_results),
                citations=compare_citations,
                artifacts=scoped_artifacts(
                    {
                        "reason": "compare_result",
                        "compare_field": compare_focus_phrase,
                        "compare_focus_query": compare_focus_query,
                        "compare_results": compare_results,
                        "compare_sources": [item["source"] for item in compare_results],
                    }
                ),
                debug={
                    **compare_resolution_debug,
                    "compare_focus_query": compare_focus_query,
                    "selected_source_ignored": bool(client_selected_source),
                    "resolved_compare_sources": [
                        _source_display_name(source)
                        for source, _doc in compare_sources
                    ],
                }
                if payload.debug
                else None,
            )
        )

    raw_results, status = retrieve(
        rewritten_query,
        k=15,
        tenant_id=tenant_id,
        return_status=True,
        source_filter=selected_source if is_document_workspace else None,
    )
    raw_distance_results = dedupe_results(raw_results)

    selection_query = original_query
    if selected_source and not is_document_workspace:
        raw_distance_results = _filter_results_to_source(raw_distance_results, selected_source)
    elif not is_document_workspace:
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
    selected_field_value = None
    selected_field_result = None
    if selected_source and _wants_bounded_answer(selection_query):
        selected_field_value, selected_field_result = _select_best_field_value_result(
            selection_query,
            results,
        )
        if selected_field_value is None:
            selected_field_value, selected_field_result = _scan_source_document_for_field_value(
                source=selected_source,
                query=selection_query,
            )
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
    if selected_field_result is not None:
        strong_evidence_results = [selected_field_result]
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
                artifacts=scoped_artifacts({"reason": "no_documents_ingested"}),
                debug={"status": status} if payload.debug else None,
            )
        )

    if not evidence_results:
        no_chunks_answer = (
            "The selected document does not answer this question."
            if is_document_workspace
            else refusal_message("no_chunks")
        )
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="hard_refusal",
                answer=no_chunks_answer,
                citations=[],
                artifacts=scoped_artifacts({"reason": "no_chunks"}),
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
        matched_document_options = [
            {
                "source": str(doc.metadata.get("source") or ""),
                "display_name": _source_display_name(doc.metadata.get("source")),
            }
            for doc, _score in plausible_source_results
        ]
        matched_documents = [
            option["display_name"]
            for option in matched_document_options
        ]
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="guided_fallback",
                answer="I found this information in multiple documents. Choose a document or ask me to compare them.",
                citations=ambiguity_citations,
                artifacts=scoped_artifacts(
                    {
                        "reason": "multiple_documents_match",
                        "matched_documents": matched_documents,
                        "matched_document_options": matched_document_options,
                    }
                ),
                debug={
                    "rewritten_query": rewritten_query,
                    "best_score": best_score,
                    "max_distance": MAX_DISTANCE,
                    "matched_documents": matched_documents,
                    "selected_source": selected_source or None,
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
        fallback_answer = (
            "No direct answer was found verbatim in the selected document. Try asking more specifically, or use keywords from that document."
            if is_document_workspace
            else "No direct answer was found verbatim in the documents. Try asking more specifically, or use keywords from the document."
        )
        return persist_and_return(
            wrap_response(
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                query=original_query,
                mode="guided_fallback",
                answer=fallback_answer,
                citations=citations,
                artifacts=scoped_artifacts(
                    {
                        "reason": "No direct answer was found in the documents for this question.",
                        "best_score": best_score,
                    }
                ),
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

    answer = (
        _build_bounded_field_direct_answer(
            query=selection_query,
            field_value=selected_field_value,
        )
        if selected_field_value
        else None
    )

    if not answer:
        answer = generate_answer(original_query, contexts)

    return persist_and_return(
        wrap_response(
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            query=original_query,
            mode="direct_answer",
            answer=answer,
            citations=citations,
            artifacts=scoped_artifacts(
                {"additional_resources": [], "best_score": best_score}
            ),
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
