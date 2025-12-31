import os
import sqlite3
from fastapi import APIRouter, Request, HTTPException

# =====================================================
# Router
# =====================================================

router = APIRouter(tags=["read"])

DB_ROOT = os.path.join("data", "tenants")
DB_FILENAME = "p1.db"


# =====================================================
# Helpers
# =====================================================

def _tenant_db_path(tenant_id: str) -> str:
    return os.path.join(DB_ROOT, tenant_id, DB_FILENAME)


def _connect(db_path: str) -> sqlite3.Connection:
    if not os.path.isfile(db_path):
        raise FileNotFoundError("Persistence DB not found")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# =====================================================
# Read APIs (READ-ONLY)
# =====================================================

@router.get("/conversations")
def list_conversations(request: Request):
    """
    Lists all conversations for the authenticated tenant.
    """
    tenant_id = request.state.tenant_id
    db_path = _tenant_db_path(tenant_id)

    try:
        conn = _connect(db_path)
    except FileNotFoundError:
        return {"tenant_id": tenant_id, "conversations": []}

    try:
        rows = conn.execute(
            """
            SELECT
              conversation_id,
              created_at,
              last_activity_at
            FROM conversations
            ORDER BY last_activity_at DESC
            """
        ).fetchall()

        conversations = [dict(row) for row in rows]

        return {
            "tenant_id": tenant_id,
            "conversations": conversations,
        }
    finally:
        conn.close()


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, request: Request):
    """
    Returns all persisted query results for a conversation.
    """
    tenant_id = request.state.tenant_id
    db_path = _tenant_db_path(tenant_id)

    try:
        conn = _connect(db_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        rows = conn.execute(
            """
            SELECT
              request_id,
              created_at,
              query,
              mode,
              answer,
              citations_json,
              artifacts_json,
              debug_json,
              response_json
            FROM queries
            WHERE tenant_id = ?
              AND conversation_id = ?
            ORDER BY created_at ASC
            """,
            (tenant_id, conversation_id),
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail="Conversation not found")

        items = [dict(row) for row in rows]

        return {
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "items": items,
        }
    finally:
        conn.close()
