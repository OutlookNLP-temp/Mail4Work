import json
import os
from datetime import datetime
from urllib.parse import unquote

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.analyze import classify, schedule, summarize
from src.db import store
from src.mail import fetch
from src.api.schemas import (
    ContactStats,
    Message,
    MessagesPayload,
    Schedule,
    Sender,
    SyncResult,
    SyncStatus,
    ThreadDetail,
    ThreadSummary,
)

load_dotenv()

app = FastAPI(title="Mail4Work API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warmup_summarizer():
    # 첫 메시지 조회 시 콜드 스타트(2~3초) 회피용으로 모델 메모리 로드 트리거
    summarize.warmup()


def _me_email() -> str:
    # ME_EMAIL이 비어있으면 IMAP_USER 사용
    return os.getenv("ME_EMAIL") or os.environ.get("IMAP_USER", "")


def _ensure_summary(
    conn,
    message_id: str,
    body: str | None,
    sender_name: str | None = None,
    direction: str = "received",
) -> str:
    # 캐시된 요약이 있으면 반환, 없으면 발신자/방향 컨텍스트와 함께 요약
    cached = store.get_summary(conn, message_id)
    if cached is not None:
        return cached
    if not body:
        return ""
    text = summarize.summarize(body, sender_name=sender_name, direction=direction)
    store.save_summary(conn, message_id, text)
    return text


def _ensure_status(conn, message_id: str, body: str | None) -> str:
    # 캐시된 상태가 있으면 반환, 없으면 키워드 분류 후 저장
    cached = store.get_status(conn, message_id)
    if cached:
        return cached["status"]
    c = classify.classify(body or "")
    store.save_status(conn, message_id, c.status, c.matched_keyword)
    return c.status


def _ensure_schedules(conn, message_id: str, body: str | None) -> list[dict]:
    # 캐시된 일정 있으면 반환, 없으면 추출 후 저장
    cached = store.get_schedules(conn, message_id)
    if cached:
        return cached
    items = schedule.extract_schedules(body or "")
    if not items:
        return []
    payload = [
        {"text": s.text, "parsed_at": s.parsed.isoformat()} for s in items
    ]
    store.replace_schedules(conn, message_id, payload)
    return payload


@app.post("/sync", response_model=SyncResult)
def sync_endpoint():
    # 사용자 트리거 동기화 — 모든 설정 폴더에서 fetch
    result = fetch.sync(limit_per_folder=int(os.getenv("FETCH_LIMIT", "50")))
    return result


@app.get("/sync/status", response_model=SyncStatus)
def sync_status():
    # 마지막 동기화 시각/메시지 수 (in_progress는 단순 false 고정 — 백그라운드 워커 없음)
    with store.connect() as conn:
        row = conn.execute(
            "SELECT MAX(last_sync_at) AS last FROM sync_state"
        ).fetchone()
        last = row["last"] if row else None
        total = store.count_messages(conn)
    return SyncStatus(
        last_sync_at=datetime.fromisoformat(last) if last else None,
        in_progress=False,
        total_messages=total,
    )


@app.get("/senders", response_model=list[Sender])
def list_senders(limit: int = 50, offset: int = 0):
    # contact 기반 — 자기 자신 제외, 최신 메일 순
    with store.connect() as conn:
        return store.list_contacts(conn, _me_email(), limit=limit, offset=offset)


@app.get(
    "/senders/{sender_id}/messages",
    response_model=MessagesPayload,
    response_model_by_alias=True,
)
def list_messages(sender_id: str, limit: int = 200, offset: int = 0):
    # URL 디코드 (sender_id가 이메일이라 @가 %40 인코딩될 수 있음)
    contact = unquote(sender_id)
    me = _me_email()
    with store.connect() as conn:
        rows = store.list_messages_with_contact(
            conn, me, contact, limit=limit, offset=offset
        )
        stats = store.get_contact_stats(conn, me, contact)

        # 메시지마다 요약 캐시 확인/생성 후 응답 구성
        messages = [
            _to_message_response(conn, row) for row in rows
        ]

    return MessagesPayload(stats=ContactStats(**stats), messages=messages)


def _to_message_response(conn, row: dict) -> Message:
    msg_id = row["message_id"]
    body = row.get("body")
    summary = _ensure_summary(
        conn,
        msg_id,
        body,
        sender_name=row.get("from_name") or row.get("from_email"),
        direction=row["direction"],
    )
    status = _ensure_status(conn, msg_id, body)
    schedules = [
        {"text": s["text"], "parsed": s["parsed_at"]}
        for s in _ensure_schedules(conn, msg_id, body)
    ]
    return Message.model_validate(
        {
            "message_id": msg_id,
            "direction": row["direction"],
            "from": row.get("from_email") or "",
            "from_name": row.get("from_name"),
            "date": row["date"],
            "subject": row.get("subject"),
            "summary": summary,
            "body": body,
            "status": status,
            "schedules": schedules,
            "attachments": [],
        }
    )


@app.get("/senders/{sender_id}/threads", response_model=list[ThreadSummary])
def list_threads_by_sender(sender_id: str, limit: int = 50, offset: int = 0):
    # 스레드 뷰용 (현재 UI 미사용이지만 추후 화면 위해 유지)
    contact = unquote(sender_id)
    with store.connect() as conn:
        rows = store.list_threads_by_sender(
            conn, contact, limit=limit, offset=offset
        )

    # 스레드 메타에 status/summary_preview/has_schedule 채워넣기
    out = []
    for r in rows:
        thread_id = r["thread_id"]
        with store.connect() as conn:
            preview, status, has_schedule = _thread_metadata(conn, thread_id)
        out.append(
            ThreadSummary(
                thread_id=thread_id,
                subject=r.get("subject") or "(제목 없음)",
                status=status,
                summary_preview=preview,
                message_count=r["message_count"],
                latest_at=r["latest_at"],
                has_schedule=has_schedule,
            )
        )
    return out


def _thread_metadata(conn, thread_id: str) -> tuple[str, str, bool]:
    # 스레드 첫 메시지 기준으로 미리보기/상태/일정 유무 산출
    msgs = store.get_thread_messages(conn, thread_id)
    if not msgs:
        return ("", "참고", False)

    first = msgs[0]
    summary = _ensure_summary(
        conn,
        first["message_id"],
        first.get("body"),
        sender_name=first.get("from_name") or first.get("from_email"),
        direction=first.get("direction", "received"),
    )

    # 상태 캐시 또는 새로 계산
    cached_status = store.get_status(conn, first["message_id"])
    if cached_status:
        status = cached_status["status"]
    else:
        c = classify.classify(first.get("body") or "")
        store.save_status(conn, first["message_id"], c.status, c.matched_keyword)
        status = c.status

    # 일정 존재 여부
    has_schedule = bool(store.get_schedules(conn, first["message_id"]))
    if not has_schedule:
        # 캐시 없으면 1회 계산 후 저장
        items = schedule.extract_schedules(first.get("body") or "")
        if items:
            store.replace_schedules(
                conn,
                first["message_id"],
                [{"text": i.text, "parsed_at": i.parsed.isoformat()} for i in items],
            )
            has_schedule = True

    return (summary[:80], status, has_schedule)


@app.get(
    "/threads/{thread_id}",
    response_model=ThreadDetail,
    response_model_by_alias=True,
)
def get_thread(thread_id: str):
    with store.connect() as conn:
        msgs = store.get_thread_messages(conn, thread_id)
        if not msgs:
            raise HTTPException(status_code=404, detail="thread not found")

        # 스레드 전체 본문을 합쳐서 한 번 요약
        combined = "\n\n".join(m.get("body") or "" for m in msgs)
        first_id = msgs[0]["message_id"]
        summary = _ensure_summary(conn, f"thread:{thread_id}", combined)

        # 스레드 단위 상태 — 첫 메시지 기준 (단순화)
        cached_status = store.get_status(conn, first_id)
        if cached_status:
            status = cached_status["status"]
        else:
            c = classify.classify(msgs[0].get("body") or "")
            store.save_status(conn, first_id, c.status, c.matched_keyword)
            status = c.status

        # 스레드 전체에서 일정 추출 (합쳐서)
        schedules_raw = schedule.extract_schedules(combined)
        schedules_out = [
            Schedule(text=s.text, parsed=s.parsed) for s in schedules_raw
        ]

        # 메시지들 — 본문 전체 노출
        messages_out = []
        for m in msgs:
            messages_out.append(
                {
                    "message_id": m["message_id"],
                    "from": m.get("from_email") or "",
                    "from_name": m.get("from_name"),
                    "to": json.loads(m.get("to_emails") or "[]"),
                    "date": m["date"],
                    "body": m.get("body") or "",
                    "attachments": [],
                }
            )

    return ThreadDetail(
        thread_id=thread_id,
        subject=msgs[0].get("subject") or "(제목 없음)",
        status=status,
        summary=summary,
        schedules=schedules_out,
        messages=messages_out,
    )


@app.get("/messages/{message_id}/attachments/{idx}")
def download_attachment(message_id: str, idx: int):
    # 첨부파일 다운로드 — IMAP에서 lazy fetch (본 PR에서는 placeholder 유지)
    return Response(
        content=b"placeholder attachment",
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="placeholder.bin"'},
    )
