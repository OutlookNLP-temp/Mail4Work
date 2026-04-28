import hashlib
import json
import sqlite3


def compute_thread_ids(conn: sqlite3.Connection) -> int:
    """References/In-Reply-To 헤더 기반으로 모든 메시지의 thread_id를 재계산.

    스레드 그룹 정책:
      - References 헤더가 있으면 첫 항목을 스레드 루트로
      - 없으면 in_reply_to를 루트로
      - 둘 다 없으면 자기 자신(rfc_message_id 또는 internal message_id)을 루트로
      - thread_id = SHA1(root)[:16]

    Returns 갱신된 메시지 개수.
    """
    rows = conn.execute(
        "SELECT message_id, rfc_message_id, in_reply_to, refs FROM messages"
    ).fetchall()

    updates: list[tuple[str, str]] = []
    for r in rows:
        # 스레드 루트 결정
        refs_raw = r["refs"]
        refs = json.loads(refs_raw) if refs_raw else []

        if refs:
            root = refs[0]
        elif r["in_reply_to"]:
            root = r["in_reply_to"]
        else:
            # 자기 자신을 루트로 (스레드 내 다른 메시지가 이걸 in_reply_to로 가지면 같은 그룹)
            root = r["rfc_message_id"] or r["message_id"]

        thread_id = _hash_thread(root)
        updates.append((thread_id, r["message_id"]))

    # 일괄 갱신
    conn.executemany(
        "UPDATE messages SET thread_id = ? WHERE message_id = ?",
        updates,
    )
    return len(updates)


def _hash_thread(root: str) -> str:
    # 16자 짧은 해시 — 충돌 가능성 낮고 URL/로그에 친화적
    return hashlib.sha1(root.encode("utf-8")).hexdigest()[:16]
