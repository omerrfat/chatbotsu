"""SQLite storage (dev + small prod). Swap for Postgres later if needed."""
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (id TEXT PRIMARY KEY, name TEXT, status TEXT DEFAULT 'active', created_at TEXT);
CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, channel TEXT NOT NULL, customer_id TEXT,
  started_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open');
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id TEXT NOT NULL, role TEXT NOT NULL,
  content TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
  fields TEXT NOT NULL, created_at TEXT NOT NULL, notified INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conv_tenant ON conversations(tenant_id);
"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    path = os.getenv("DB_PATH", str(Path(__file__).resolve().parent.parent / "data" / "chatbot.db"))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def new_conversation(conn, tenant_id, channel, customer_id=None) -> str:
    cid = uuid.uuid4().hex
    conn.execute("INSERT INTO conversations (id, tenant_id, channel, customer_id, started_at) VALUES (?,?,?,?,?)",
                 (cid, tenant_id, channel, customer_id, _now()))
    conn.commit()
    return cid


def get_conversation(conn, cid, tenant_id):
    """Only returns the conversation if it belongs to this tenant."""
    return conn.execute("SELECT * FROM conversations WHERE id=? AND tenant_id=?", (cid, tenant_id)).fetchone()


def add_message(conn, cid, role, content):
    conn.execute("INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?,?,?,?)",
                 (cid, role, content, _now()))
    conn.commit()


def get_history(conn, cid, limit=40) -> list[dict]:
    rows = conn.execute("SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                        (cid, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


def count_messages(conn, cid) -> int:
    return conn.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=?", (cid,)).fetchone()[0]


def set_status(conn, cid, status):
    conn.execute("UPDATE conversations SET status=? WHERE id=?", (status, cid))
    conn.commit()


def has_lead(conn, cid) -> bool:
    return conn.execute("SELECT 1 FROM leads WHERE conversation_id=?", (cid,)).fetchone() is not None


def add_lead(conn, tenant_id, cid, fields: dict) -> int:
    cur = conn.execute("INSERT INTO leads (tenant_id, conversation_id, fields, created_at) VALUES (?,?,?,?)",
                       (tenant_id, cid, json.dumps(fields, ensure_ascii=False), _now()))
    conn.commit()
    return cur.lastrowid


def mark_notified(conn, lead_id):
    conn.execute("UPDATE leads SET notified=1 WHERE id=?", (lead_id,))
    conn.commit()
