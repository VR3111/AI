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
def build_citations(results: list[tuple[Any, float]]) -> list[dict]:
    citations: list[dict] = []
    for doc, score in results:
        citations.append(
            {
                "source": doc.metadata.get("source"),
                "page": doc.metadata.get("page"),
                "score": score,
                "snippet": (doc.page_content or "")[:300],
            }
        )
    return citations


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
                debug={"status": status} if payload.debug else None,
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
                debug={
                    "status": status,
                    "rewritten_query": rewritten_query,
                    "results_count": 0,
                }
                if payload.debug
                else None,
            )
        )

    best_score = min(score for _, score in results)
    citations = build_citations(results)

    # ---------------- fallback logic ----------------
    # IMPORTANT CHANGE:
    # - If we HAVE chunks, we should NOT return blank answer.
    # - We will still show citations + chunk evidence.
    if is_explanatory_query(original_query) or best_score > MAX_DISTANCE:
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
                    "results_count": len(results),
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
            citations=citations,
            artifacts={"additional_resources": [], "best_score": best_score},
            debug={
                "rewritten_query": rewritten_query,
                "best_score": best_score,
                "max_distance": MAX_DISTANCE,
                "results_count": len(results),
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
