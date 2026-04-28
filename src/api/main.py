from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from src.api import mocks
from src.api.schemas import (
    Sender,
    SyncResult,
    SyncStatus,
    ThreadDetail,
    ThreadSummary,
)

app = FastAPI(title="Mail4Work API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/sync", response_model=SyncResult)
def sync():
    return mocks.SYNC_RESULT


@app.get("/sync/status", response_model=SyncStatus)
def sync_status():
    return mocks.SYNC_STATUS


@app.get("/senders", response_model=list[Sender])
def list_senders(limit: int = 50, offset: int = 0):
    return mocks.SENDERS[offset : offset + limit]


@app.get("/senders/{sender_id}/threads", response_model=list[ThreadSummary])
def list_threads_by_sender(sender_id: str, limit: int = 50, offset: int = 0):
    threads = mocks.THREADS_BY_SENDER.get(sender_id, [])
    return threads[offset : offset + limit]


@app.get(
    "/threads/{thread_id}",
    response_model=ThreadDetail,
    response_model_by_alias=True,
)
def get_thread(thread_id: str):
    thread = mocks.THREADS.get(thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return thread


@app.get("/messages/{message_id}/attachments/{idx}")
def download_attachment(message_id: str, idx: int):
    return Response(
        content=b"mock attachment content",
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="mock.txt"'},
    )
