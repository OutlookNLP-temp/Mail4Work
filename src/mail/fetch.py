import os
from datetime import datetime

from dotenv import load_dotenv
from imap_tools import AND, MailBox

from src.db import store
from src.mail.grouping import compute_thread_ids


def sync(limit_per_folder: int | None = None) -> dict:
    """설정된 모든 폴더에서 새 메시지를 가져와 SQLite에 저장한다.

    각 폴더별로 last_uid 이후 메시지만 가져온다.
    """
    load_dotenv()
    host = os.environ["IMAP_HOST"]
    user = os.environ["IMAP_USER"]
    password = os.environ["IMAP_PASSWORD"]
    folders = _parse_folders(os.getenv("IMAP_FOLDERS", "INBOX"))

    store.init_db()
    started_at = datetime.now()
    total_fetched = 0
    per_folder: dict[str, int] = {}

    with MailBox(host).login(user, password) as mailbox:
        for folder in folders:
            try:
                fetched = _sync_folder(mailbox, folder, limit_per_folder)
            except Exception as e:
                # 한 폴더 실패해도 나머지 진행 (없는 폴더 등)
                print(f"⚠️  {folder} 동기화 실패: {e}")
                fetched = 0
            per_folder[folder] = fetched
            total_fetched += fetched

    # 모든 폴더 동기화 후 스레드 그룹 재계산
    with store.connect() as conn:
        compute_thread_ids(conn)
        total_in_db = store.count_messages(conn)

    finished_at = datetime.now()
    return {
        "fetched": total_fetched,
        "per_folder": per_folder,
        "total": total_in_db,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _sync_folder(mailbox: MailBox, folder: str, limit: int | None) -> int:
    # 폴더 진입
    mailbox.folder.set(folder)

    fetched = 0
    with store.connect() as conn:
        last_uid = store.get_last_uid(conn, folder)
        # 첫 sync면 최신부터, 이후엔 last_uid 이후 새 메일만 (UID 순)
        is_first_sync = last_uid == 0
        if is_first_sync:
            criteria = AND(all=True)
        else:
            criteria = AND(uid=f"{last_uid + 1}:*")

        new_last_uid = last_uid
        for msg in mailbox.fetch(
            criteria, limit=limit, mark_seen=False, reverse=is_first_sync
        ):
            uid = int(msg.uid)
            store.upsert_message(conn, _to_record(msg, folder, uid))
            fetched += 1
            if uid > new_last_uid:
                new_last_uid = uid

        store.update_sync_state(conn, folder, new_last_uid)

    return fetched


def _parse_folders(raw: str) -> list[str]:
    # 콤마 구분 + 공백 트림 + 빈 항목 제거
    return [f.strip() for f in raw.split(",") if f.strip()]


def _to_record(msg, folder: str, uid: int) -> dict:
    # In-Reply-To 헤더 추출 (단일 Message-ID)
    in_reply_to = None
    irt = msg.headers.get("in-reply-to")
    if irt:
        in_reply_to = irt[0].strip()

    # References 헤더 추출 (공백 구분된 Message-ID 리스트)
    refs: list[str] = []
    refs_header = msg.headers.get("references")
    if refs_header:
        refs = refs_header[0].split()

    # 메일 자체의 RFC Message-ID — 스레드 매칭에 필요
    rfc_message_id = None
    mid = msg.headers.get("message-id")
    if mid:
        rfc_message_id = mid[0].strip()

    from_email = msg.from_values.email if msg.from_values else msg.from_
    from_name = msg.from_values.name if msg.from_values else None

    return {
        "message_id": f"{folder}:{uid}",
        "folder": folder,
        "uid": uid,
        "rfc_message_id": rfc_message_id,
        "subject": msg.subject,
        "from_email": from_email,
        "from_name": from_name,
        "to_emails": list(msg.to),
        "date": msg.date,
        "body": msg.text or msg.html or "",
        "in_reply_to": in_reply_to,
        "refs": refs,
        "has_attachments": len(msg.attachments) > 0,
    }


def main():
    # FETCH_LIMIT 등 환경변수 읽기 전 .env 먼저 로드
    load_dotenv()
    limit_env = os.getenv("FETCH_LIMIT", "50")
    limit = int(limit_env) if limit_env else None

    result = sync(limit_per_folder=limit)
    duration = (result["finished_at"] - result["started_at"]).total_seconds()
    print(f"Fetched : {result['fetched']} (per folder: {result['per_folder']})")
    print(f"In DB   : {result['total']}")
    print(f"Duration: {duration:.1f}s")


if __name__ == "__main__":
    main()
