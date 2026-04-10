import os
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Optional

DB_ROOT = os.path.join("data", "tenants")
DB_FILENAME = "p1.db"


# ----------------------------
# Paths / connections
# ----------------------------
def _tenant_db_path(tenant_id: str) -> str:
    return os.path.join(DB_ROOT, tenant_id, DB_FILENAME)


def _connect(db_path: str) -> sqlite3.Connection:
    # Autocommit mode for simplicity + durability
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.row_factory = sqlite3.Row

    # Safer concurrent reads/writes + fewer "database is locked" issues
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.execute("PRAGMA busy_timeout=5000;")  # 5s

    return conn


# ----------------------------
# Schema
# ----------------------------
_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
  tenant_id TEXT NOT NULL,
  conversation_id TEXT NOT NULL,
  title TEXT,
  created_at TEXT NOT NULL,
  last_activity_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, conversation_id)
);

CREATE TABLE IF NOT EXISTS queries (
  tenant_id TEXT NOT NULL,
  request_id TEXT NOT NULL,
  conversation_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  query TEXT NOT NULL,
  mode TEXT NOT NULL,
  answer TEXT NOT NULL,
  citations_json TEXT NOT NULL,
  artifacts_json TEXT NOT NULL,
  debug_json TEXT,
  response_json TEXT NOT NULL,
  PRIMARY KEY (tenant_id, request_id),
  FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations(tenant_id, conversation_id)
    ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_queries_conv_created
  ON queries(tenant_id, conversation_id, created_at);

CREATE TABLE IF NOT EXISTS document_analyses (
  tenant_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  source_path TEXT NOT NULL,
  source_sha256 TEXT NOT NULL,
  file_size_bytes INTEGER NOT NULL,
  file_mtime REAL NOT NULL,
  analysis_version TEXT NOT NULL,
  status TEXT NOT NULL,
  parser_json TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  sections_json TEXT NOT NULL,
  clauses_json TEXT NOT NULL,
  entities_json TEXT NOT NULL,
  risks_json TEXT NOT NULL,
  error_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (tenant_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_document_analyses_updated
  ON document_analyses(tenant_id, updated_at);
"""

_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def _to_title_case(word: str) -> str:
    return word[:1].upper() + word[1:]


def generate_conversation_title(query: str) -> str:
    normalized = (
        query.lower()
        .replace("’", "'")
    )
    normalized = re.sub(r"(?!\B'\B)[^\w\s']", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if not normalized:
        return ""

    words = [word for word in normalized.split(" ") if word]
    filtered_words = [word for word in words if word not in _TITLE_STOPWORDS]
    source_words = filtered_words if filtered_words else words

    if len(source_words) < 3 and filtered_words:
        source_words = filtered_words

    title = " ".join(_to_title_case(word) for word in source_words[:6])
    if len(title) <= 32:
        return title

    return f"{title[:31].rstrip()}…"


def _ensure_conversation_title_column(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
    }
    if "title" not in columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN title TEXT")


def _backfill_missing_conversation_titles(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT tenant_id, conversation_id
        FROM conversations
        WHERE title IS NULL OR TRIM(title) = ''
        """
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
            (row["tenant_id"], row["conversation_id"]),
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
            (title, row["tenant_id"], row["conversation_id"]),
        )


def _ensure_document_analysis_columns(conn: sqlite3.Connection) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(document_analyses)").fetchall()
    }
    if columns and "metadata_json" not in columns:
        conn.execute(
            "ALTER TABLE document_analyses ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"
        )
    if columns and "sections_json" not in columns:
        conn.execute(
            "ALTER TABLE document_analyses ADD COLUMN sections_json TEXT NOT NULL DEFAULT '[]'"
        )
    if columns and "risks_json" not in columns:
        conn.execute(
            "ALTER TABLE document_analyses ADD COLUMN risks_json TEXT NOT NULL DEFAULT '[]'"
        )


def init_db(tenant_id: str) -> str:
    """
    Ensures the tenant DB exists and schema is applied.
    Returns the DB path.
    """
    if not tenant_id or not isinstance(tenant_id, str):
        raise ValueError("tenant_id is required")

    tenant_dir = os.path.join(DB_ROOT, tenant_id)
    os.makedirs(tenant_dir, exist_ok=True)

    db_path = _tenant_db_path(tenant_id)
    conn = _connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        _ensure_conversation_title_column(conn)
        _ensure_document_analysis_columns(conn)
        _backfill_missing_conversation_titles(conn)
    finally:
        conn.close()

    return db_path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_json(raw_value: Any, default: Any) -> Any:
    if raw_value in (None, ""):
        return default
    try:
        return json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return default


def _hydrate_document_analysis(row: sqlite3.Row | None) -> Optional[Dict[str, Any]]:
    if not row:
        return None

    payload = dict(row)
    payload["parser"] = _decode_json(payload.pop("parser_json", None), {})
    payload["metadata"] = _decode_json(payload.pop("metadata_json", None), {})
    payload["sections"] = _decode_json(payload.pop("sections_json", None), [])
    payload["clauses"] = _decode_json(payload.pop("clauses_json", None), [])
    payload["entities"] = _decode_json(payload.pop("entities_json", None), [])
    payload["risks"] = _decode_json(payload.pop("risks_json", None), [])
    return payload


# ----------------------------
# Public API (Option A)
# ----------------------------
def save_query_result(*, tenant_id: str, conversation_id: str, payload: Dict[str, Any]) -> None:
    """
    Persists a final /query response (already wrapped).
    Stores:
      - conversation row (upsert)
      - query row keyed by (tenant_id, request_id)

    IMPORTANT: caller must pass tenant_id from request.state.tenant_id (authoritative).
    """
    if not tenant_id or not conversation_id:
        raise ValueError("tenant_id and conversation_id are required")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")

    # Defensive: rely on response fields (API contract)
    request_id = str(payload.get("request_id", ""))
    created_at = str(payload.get("created_at", ""))

    if not request_id or not created_at:
        raise ValueError("payload missing request_id/created_at")

    query_text = str(payload.get("query", ""))
    mode = str(payload.get("mode", ""))
    answer = str(payload.get("answer", ""))

    citations = payload.get("citations", [])
    artifacts = payload.get("artifacts", {})
    debug = payload.get("debug", None)

    citations_json = json.dumps(citations, ensure_ascii=False)
    artifacts_json = json.dumps(artifacts, ensure_ascii=False)
    debug_json = json.dumps(debug, ensure_ascii=False) if debug is not None else None
    response_json = json.dumps(payload, ensure_ascii=False)

    db_path = init_db(tenant_id)
    conn = _connect(db_path)

    try:
        conn.execute("BEGIN")

        # Upsert conversation
        conn.execute(
            """
            INSERT INTO conversations (
              tenant_id, conversation_id, title, created_at, last_activity_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, conversation_id) DO UPDATE SET
              last_activity_at = excluded.last_activity_at
            """,
            (
                tenant_id,
                conversation_id,
                generate_conversation_title(query_text) or None,
                created_at,
                created_at,
            ),
        )

        # Insert query record (idempotent per request_id)
        conn.execute(
            """
            INSERT OR IGNORE INTO queries (
              tenant_id, request_id, conversation_id, created_at,
              query, mode, answer,
              citations_json, artifacts_json, debug_json, response_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tenant_id,
                request_id,
                conversation_id,
                created_at,
                query_text,
                mode,
                answer,
                citations_json,
                artifacts_json,
                debug_json,
                response_json,
            ),
        )

        _backfill_missing_conversation_titles(conn)
        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_document_analysis(tenant_id: str, document_id: str) -> Optional[Dict[str, Any]]:
    db_path = init_db(tenant_id)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT *
            FROM document_analyses
            WHERE tenant_id = ?
              AND document_id = ?
            """,
            (tenant_id, document_id),
        ).fetchone()
        return _hydrate_document_analysis(row)
    finally:
        conn.close()


def upsert_document_analysis(
    *,
    tenant_id: str,
    document_id: str,
    filename: str,
    source_path: str,
    source_sha256: str,
    file_size_bytes: int,
    file_mtime: float,
    analysis_version: str,
    status: str,
    parser_payload: Dict[str, Any] | None,
    metadata_payload: Dict[str, Any] | None,
    sections: list[Dict[str, Any]] | None,
    clauses: list[Dict[str, Any]] | None,
    entities: list[Dict[str, Any]] | None,
    risks: list[Dict[str, Any]] | None = None,
    error_message: str | None = None,
) -> None:
    db_path = init_db(tenant_id)
    conn = _connect(db_path)
    now = _now_iso()

    parser_json = json.dumps(parser_payload or {}, ensure_ascii=False)
    metadata_json = json.dumps(metadata_payload or {}, ensure_ascii=False)
    sections_json = json.dumps(sections or [], ensure_ascii=False)
    clauses_json = json.dumps(clauses or [], ensure_ascii=False)
    entities_json = json.dumps(entities or [], ensure_ascii=False)
    risks_json = json.dumps(risks or [], ensure_ascii=False)

    try:
        conn.execute(
            """
            INSERT INTO document_analyses (
              tenant_id, document_id, filename, source_path, source_sha256,
              file_size_bytes, file_mtime, analysis_version, status,
              parser_json, metadata_json, sections_json, clauses_json, entities_json,
              risks_json, error_message,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, document_id) DO UPDATE SET
              filename = excluded.filename,
              source_path = excluded.source_path,
              source_sha256 = excluded.source_sha256,
              file_size_bytes = excluded.file_size_bytes,
              file_mtime = excluded.file_mtime,
              analysis_version = excluded.analysis_version,
              status = excluded.status,
              parser_json = excluded.parser_json,
              metadata_json = excluded.metadata_json,
              sections_json = excluded.sections_json,
              clauses_json = excluded.clauses_json,
              entities_json = excluded.entities_json,
              risks_json = excluded.risks_json,
              error_message = excluded.error_message,
              updated_at = excluded.updated_at
            """,
            (
                tenant_id,
                document_id,
                filename,
                source_path,
                source_sha256,
                file_size_bytes,
                file_mtime,
                analysis_version,
                status,
                parser_json,
                metadata_json,
                sections_json,
                clauses_json,
                entities_json,
                risks_json,
                error_message,
                now,
                now,
            ),
        )
    finally:
        conn.close()


def delete_document_analysis(tenant_id: str, document_id: str) -> None:
    db_path = init_db(tenant_id)
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            DELETE FROM document_analyses
            WHERE tenant_id = ?
              AND document_id = ?
            """,
            (tenant_id, document_id),
        )
    finally:
        conn.close()


def prune_document_analyses(tenant_id: str, active_document_ids: set[str]) -> None:
    db_path = init_db(tenant_id)
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT document_id
            FROM document_analyses
            WHERE tenant_id = ?
            """,
            (tenant_id,),
        ).fetchall()
        stale_document_ids = [
            str(row["document_id"])
            for row in rows
            if str(row["document_id"]) not in active_document_ids
        ]
        for document_id in stale_document_ids:
            conn.execute(
                """
                DELETE FROM document_analyses
                WHERE tenant_id = ?
                  AND document_id = ?
                """,
                (tenant_id, document_id),
            )
    finally:
        conn.close()


def transfer_conversations(*, source_tenant_id: str, target_tenant_id: str) -> int:
    if not source_tenant_id or not target_tenant_id:
        raise ValueError("source_tenant_id and target_tenant_id are required")
    if source_tenant_id == target_tenant_id:
        return 0

    source_db_path = _tenant_db_path(source_tenant_id)
    if not os.path.isfile(source_db_path):
        return 0

    target_db_path = init_db(target_tenant_id)
    target_conn = _connect(target_db_path)

    try:
        existing_count_row = target_conn.execute(
            "SELECT COUNT(*) AS count FROM conversations WHERE tenant_id = ?",
            (target_tenant_id,),
        ).fetchone()
        existing_count = int(existing_count_row["count"]) if existing_count_row else 0
        if existing_count > 0:
            return -1

        source_conn = _connect(source_db_path)
        try:
            source_conversations = source_conn.execute(
                """
                SELECT conversation_id, title, created_at, last_activity_at
                FROM conversations
                WHERE tenant_id = ?
                ORDER BY created_at ASC
                """,
                (source_tenant_id,),
            ).fetchall()

            if not source_conversations:
                return 0

            source_queries = source_conn.execute(
                """
                SELECT
                  request_id,
                  conversation_id,
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
                ORDER BY created_at ASC
                """,
                (source_tenant_id,),
            ).fetchall()
        finally:
            source_conn.close()

        target_conn.execute("BEGIN")
        try:
            for row in source_conversations:
                target_conn.execute(
                    """
                    INSERT INTO conversations (
                      tenant_id, conversation_id, title, created_at, last_activity_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        target_tenant_id,
                        row["conversation_id"],
                        row["title"],
                        row["created_at"],
                        row["last_activity_at"],
                    ),
                )

            for row in source_queries:
                target_conn.execute(
                    """
                    INSERT INTO queries (
                      tenant_id, request_id, conversation_id, created_at,
                      query, mode, answer, citations_json, artifacts_json,
                      debug_json, response_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        target_tenant_id,
                        row["request_id"],
                        row["conversation_id"],
                        row["created_at"],
                        row["query"],
                        row["mode"],
                        row["answer"],
                        row["citations_json"],
                        row["artifacts_json"],
                        row["debug_json"],
                        row["response_json"],
                    ),
                )
            target_conn.commit()
        except Exception:
            target_conn.rollback()
            raise

        return len(source_conversations)
    finally:
        target_conn.close()


def delete_tenant_data(tenant_id: str) -> None:
    if not tenant_id:
        raise ValueError("tenant_id is required")

    tenant_dir = os.path.join(DB_ROOT, tenant_id)
    if os.path.isdir(tenant_dir):
        shutil.rmtree(tenant_dir)
