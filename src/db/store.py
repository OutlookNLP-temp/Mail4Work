import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path("data/mail4work.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    folder TEXT NOT NULL,
    uid INTEGER NOT NULL,
    subject TEXT,
    from_email TEXT,
    from_name TEXT,
    to_emails TEXT NOT NULL DEFAULT '[]',
    date TEXT,
    body TEXT,
    in_reply_to TEXT,
    refs TEXT NOT NULL DEFAULT '[]',
    has_attachments INTEGER NOT NULL DEFAULT 0,
    fetched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_from ON messages(from_email);
CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date);

CREATE TABLE IF NOT EXISTS sync_state (
    folder TEXT PRIMARY KEY,
    last_uid INTEGER NOT NULL DEFAULT 0,
    last_sync_at TEXT
);
"""


def init_db(path: Path = DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def connect(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_message(conn: sqlite3.Connection, m: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO messages (
            message_id, folder, uid, subject, from_email, from_name,
            to_emails, date, body, in_reply_to, refs, has_attachments
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            m["message_id"],
            m["folder"],
            m["uid"],
            m.get("subject"),
            m.get("from_email"),
            m.get("from_name"),
            json.dumps(m.get("to_emails") or []),
            m["date"].isoformat() if m.get("date") else None,
            m.get("body"),
            m.get("in_reply_to"),
            json.dumps(m.get("refs") or []),
            1 if m.get("has_attachments") else 0,
        ),
    )


def get_last_uid(conn: sqlite3.Connection, folder: str) -> int:
    row = conn.execute(
        "SELECT last_uid FROM sync_state WHERE folder = ?", (folder,)
    ).fetchone()
    return row["last_uid"] if row else 0


def update_sync_state(
    conn: sqlite3.Connection, folder: str, last_uid: int
) -> None:
    conn.execute(
        """
        INSERT INTO sync_state (folder, last_uid, last_sync_at)
        VALUES (?, ?, ?)
        ON CONFLICT(folder) DO UPDATE SET
            last_uid = excluded.last_uid,
            last_sync_at = excluded.last_sync_at
        """,
        (folder, last_uid, datetime.now().isoformat()),
    )


def count_messages(
    conn: sqlite3.Connection, folder: str | None = None
) -> int:
    if folder:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM messages WHERE folder = ?", (folder,)
        ).fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()
    return row["c"]
