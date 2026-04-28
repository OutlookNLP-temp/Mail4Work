import os
from datetime import datetime

from dotenv import load_dotenv
from imap_tools import AND, MailBox

from src.db import store


def sync(limit: int | None = None) -> dict:
    """IMAP에서 새 메일을 가져와 SQLite에 저장한다.

    last_uid 이후 메시지만 가져오며, limit이 있으면 그 개수까지만 fetch.
    """
    load_dotenv()
    host = os.environ["IMAP_HOST"]
    user = os.environ["IMAP_USER"]
    password = os.environ["IMAP_PASSWORD"]
    folder = os.getenv("IMAP_FOLDER", "INBOX")

    store.init_db()
    started_at = datetime.now()
    fetched = 0

    with store.connect() as conn:
        last_uid = store.get_last_uid(conn, folder)
        criteria = AND(uid=f"{last_uid + 1}:*") if last_uid > 0 else AND(all=True)

        new_last_uid = last_uid
        with MailBox(host).login(user, password, initial_folder=folder) as mailbox:
            for msg in mailbox.fetch(criteria, limit=limit, mark_seen=False):
                uid = int(msg.uid)
                store.upsert_message(conn, _to_record(msg, folder, uid))
                fetched += 1
                if uid > new_last_uid:
                    new_last_uid = uid

        store.update_sync_state(conn, folder, new_last_uid)
        total = store.count_messages(conn, folder)

    finished_at = datetime.now()
    return {
        "fetched": fetched,
        "total": total,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def _to_record(msg, folder: str, uid: int) -> dict:
    in_reply_to = None
    irt = msg.headers.get("in-reply-to")
    if irt:
        in_reply_to = irt[0].strip()

    refs: list[str] = []
    refs_header = msg.headers.get("references")
    if refs_header:
        refs = refs_header[0].split()

    from_email = msg.from_values.email if msg.from_values else msg.from_
    from_name = msg.from_values.name if msg.from_values else None

    return {
        "message_id": f"{folder}:{uid}",
        "folder": folder,
        "uid": uid,
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
    limit_env = os.getenv("FETCH_LIMIT", "50")
    limit = int(limit_env) if limit_env else None

    result = sync(limit=limit)
    duration = (result["finished_at"] - result["started_at"]).total_seconds()
    print(f"Fetched : {result['fetched']}")
    print(f"In DB   : {result['total']}")
    print(f"Duration: {duration:.1f}s")


if __name__ == "__main__":
    main()
