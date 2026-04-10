import os
import sqlite3
import json
from fastapi import APIRouter, Request, HTTPException
from app.persist import generate_conversation_title, get_document_analysis

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
              c.conversation_id,
              c.title,
              c.created_at,
              c.last_activity_at,
              q.artifacts_json AS latest_artifacts_json
            FROM conversations c
            LEFT JOIN queries q
              ON q.tenant_id = c.tenant_id
             AND q.conversation_id = c.conversation_id
             AND q.created_at = (
                SELECT MAX(q2.created_at)
                FROM queries q2
                WHERE q2.tenant_id = c.tenant_id
                  AND q2.conversation_id = c.conversation_id
             )
            ORDER BY last_activity_at DESC
            """
        ).fetchall()

        conversations = []
        for row in rows:
            conversation = dict(row)
            artifacts_json = conversation.pop("latest_artifacts_json", None)
            artifacts = {}
            if artifacts_json:
                try:
                    artifacts = json.loads(artifacts_json)
                except json.JSONDecodeError:
                    artifacts = {}

            selected_source = artifacts.get("selected_source")
            if isinstance(selected_source, str) and selected_source.strip():
                conversation["selected_source"] = selected_source.strip()
                conversation["selected_source_display_name"] = str(
                    artifacts.get("selected_source_display_name") or ""
                ).strip() or os.path.basename(selected_source.strip())
                workspace_scope = str(artifacts.get("workspace_scope") or "global").strip().lower()
                conversation["workspace_scope"] = (
                    workspace_scope if workspace_scope in {"global", "document"} else "global"
                )

            conversations.append(conversation)

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


@router.get("/documents/{document_id}/structure")
def get_document_structure(document_id: str, request: Request):
    tenant_id = request.state.tenant_id
    analysis = get_document_analysis(tenant_id, document_id)

    if not analysis:
        raise HTTPException(status_code=404, detail="Structured document not found")

    return {
        "tenant_id": tenant_id,
        "document_id": document_id,
        "filename": analysis.get("filename"),
        "status": analysis.get("status"),
        "analysis_version": analysis.get("analysis_version"),
        "updated_at": analysis.get("updated_at"),
        "error_message": analysis.get("error_message"),
        "metadata": analysis.get("metadata") or {},
        "sections": analysis.get("sections") or [],
        "clauses": analysis.get("clauses") or [],
        "entities": analysis.get("entities") or [],
        "risks": analysis.get("risks") or [],
    }


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
