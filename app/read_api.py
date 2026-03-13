import os
import sqlite3
from fastapi import APIRouter, Request, HTTPException
from app.persist import generate_conversation_title

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


def _ensure_conversation_title_column(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if "title" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN title TEXT")


def _backfill_missing_conversation_titles(
    conn: sqlite3.Connection, tenant_id: str
) -> None:
    rows = conn.execute(
        """
        SELECT conversation_id
        FROM conversations
        WHERE tenant_id = ?
          AND (title IS NULL OR TRIM(title) = '')
        """,
        (tenant_id,),
    ).fetchall()

    for row in rows:
        first_query_row = conn.execute(
            """
            SELECT query
            FROM queries
            WHERE tenant_id = ?
              AND conversation_id = ?
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (tenant_id, row["conversation_id"]),
        ).fetchone()

        if not first_query_row:
            continue

        title = generate_conversation_title(str(first_query_row["query"] or ""))
        if not title:
            continue

        conn.execute(
            """
            UPDATE conversations
            SET title = ?
            WHERE tenant_id = ?
              AND conversation_id = ?
              AND (title IS NULL OR TRIM(title) = '')
            """,
            (title, tenant_id, row["conversation_id"]),
        )


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
        _ensure_conversation_title_column(conn)
        _backfill_missing_conversation_titles(conn, tenant_id)
        rows = conn.execute(
            """
            SELECT
              conversation_id,
              title,
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


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, request: Request):
    """
    Deletes a conversation and all its persisted query rows for the authenticated tenant.
    """
    tenant_id = request.state.tenant_id
    db_path = _tenant_db_path(tenant_id)

    try:
        conn = _connect(db_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        conn.execute(
            """
            DELETE FROM queries
            WHERE tenant_id = ?
              AND conversation_id = ?
            """,
            (tenant_id, conversation_id),
        )

        conn.execute(
            """
            DELETE FROM conversations
            WHERE tenant_id = ?
              AND conversation_id = ?
            """,
            (tenant_id, conversation_id),
        )
        conn.commit()

        return {"status": "deleted"}
    finally:
        conn.close()
