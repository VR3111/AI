import os
import json
import sqlite3
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
"""


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
    finally:
        conn.close()

    return db_path


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
        # Upsert conversation
        conn.execute(
            """
            INSERT INTO conversations (tenant_id, conversation_id, created_at, last_activity_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tenant_id, conversation_id) DO UPDATE SET
              last_activity_at=excluded.last_activity_at
            """,
            (tenant_id, conversation_id, created_at, created_at),
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

    finally:
        conn.close()
