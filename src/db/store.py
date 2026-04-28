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

CREATE TABLE IF NOT EXISTS summaries (
    message_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS message_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL,
    text TEXT NOT NULL,
    parsed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(message_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_schedules_message ON message_schedules(message_id);
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


def get_summary(conn: sqlite3.Connection, message_id: str) -> str | None:
    # 캐시된 요약 조회 (없으면 None)
    row = conn.execute(
        "SELECT summary FROM summaries WHERE message_id = ?", (message_id,)
    ).fetchone()
    return row["summary"] if row else None


def save_summary(
    conn: sqlite3.Connection, message_id: str, summary: str
) -> None:
    # 요약 upsert (있으면 덮어쓰고 created_at 갱신)
    conn.execute(
        """
        INSERT INTO summaries (message_id, summary)
        VALUES (?, ?)
        ON CONFLICT(message_id) DO UPDATE SET
            summary = excluded.summary,
            created_at = CURRENT_TIMESTAMP
        """,
        (message_id, summary),
    )


def get_schedules(
    conn: sqlite3.Connection, message_id: str
) -> list[dict]:
    # 메시지의 추출된 일정 리스트 조회
    rows = conn.execute(
        "SELECT text, parsed_at FROM message_schedules "
        "WHERE message_id = ? ORDER BY parsed_at",
        (message_id,),
    ).fetchall()
    return [{"text": r["text"], "parsed_at": r["parsed_at"]} for r in rows]


def replace_schedules(
    conn: sqlite3.Connection,
    message_id: str,
    schedules: list[dict],
) -> None:
    # 메시지의 일정 전체 교체 (재추출 시 깔끔하게 갱신)
    conn.execute(
        "DELETE FROM message_schedules WHERE message_id = ?", (message_id,)
    )
    for s in schedules:
        conn.execute(
            "INSERT INTO message_schedules (message_id, text, parsed_at) "
            "VALUES (?, ?, ?)",
            (message_id, s["text"], s["parsed_at"]),
        )
