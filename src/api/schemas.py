from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class SyncResult(BaseModel):
    fetched: int
    per_folder: dict[str, int] = {}
    total: int
    started_at: datetime
    finished_at: datetime


class SyncStatus(BaseModel):
    last_sync_at: datetime | None
    in_progress: bool
    total_messages: int


class Sender(BaseModel):
    sender_id: str
    name: str | None = None
    email: str
    message_count: int
    latest_at: datetime


class ContactStats(BaseModel):
    total: int
    sent: int
    received: int


class Attachment(BaseModel):
    idx: int
    filename: str
    size: int


class Message(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str
    direction: str
    from_: str = Field(alias="from")
    from_name: str | None = None
    date: datetime
    subject: str | None = None
    summary: str | None = None
    body: str | None = None
    attachments: list[Attachment] = []


class MessagesPayload(BaseModel):
    stats: ContactStats
    messages: list[Message]


class ThreadSummary(BaseModel):
    thread_id: str
    subject: str
    status: str
    summary_preview: str
    message_count: int
    latest_at: datetime
    has_schedule: bool


class Schedule(BaseModel):
    text: str
    parsed: datetime


class MessageDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message_id: str
    from_: str = Field(alias="from")
    from_name: str | None = None
    to: list[str]
    date: datetime
    body: str
    attachments: list[Attachment] = []


class ThreadDetail(BaseModel):
    thread_id: str
    subject: str
    status: str
    summary: str
    schedules: list[Schedule] = []
    messages: list[MessageDetail]
