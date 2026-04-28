from datetime import datetime

from src.api.schemas import (
    Attachment,
    MessageDetail,
    Schedule,
    Sender,
    SyncResult,
    SyncStatus,
    ThreadDetail,
    ThreadSummary,
)


SYNC_RESULT = SyncResult(
    fetched=12,
    total=348,
    started_at=datetime(2026, 4, 28, 10, 30, 0),
    finished_at=datetime(2026, 4, 28, 10, 30, 8),
)

SYNC_STATUS = SyncStatus(
    last_sync_at=datetime(2026, 4, 28, 10, 30, 8),
    in_progress=False,
    total_messages=348,
)

SENDERS: list[Sender] = [
    Sender(
        sender_id="boss@company.com",
        name="김부장",
        email="boss@company.com",
        thread_count=12,
        unread_count=3,
        latest_at=datetime(2026, 4, 28, 10, 30, 0),
    ),
    Sender(
        sender_id="newsletter@tech.com",
        name="Tech Weekly",
        email="newsletter@tech.com",
        thread_count=8,
        unread_count=0,
        latest_at=datetime(2026, 4, 27, 9, 0, 0),
    ),
    Sender(
        sender_id="hr@company.com",
        name="인사팀",
        email="hr@company.com",
        thread_count=3,
        unread_count=1,
        latest_at=datetime(2026, 4, 26, 14, 20, 0),
    ),
]

THREADS_BY_SENDER: dict[str, list[ThreadSummary]] = {
    "boss@company.com": [
        ThreadSummary(
            thread_id="a3f9b2c1d4e5f6a7",
            subject="프로젝트 일정 논의",
            status="회신 필요",
            summary_preview="프로젝트 기획안 검토 후 다음 주 미팅 일정 확정 요청",
            message_count=4,
            latest_at=datetime(2026, 4, 28, 10, 30, 0),
            has_schedule=True,
        ),
        ThreadSummary(
            thread_id="b2e8a1d0c3f4e5b6",
            subject="주간 리포트",
            status="완료",
            summary_preview="이번 주 진행 상황 보고 완료",
            message_count=2,
            latest_at=datetime(2026, 4, 25, 17, 0, 0),
            has_schedule=False,
        ),
    ],
    "newsletter@tech.com": [
        ThreadSummary(
            thread_id="c1d7e6f5a4b3c2d1",
            subject="이번 주의 AI 뉴스",
            status="참고",
            summary_preview="LLM 최신 동향과 오픈소스 모델 업데이트 소식",
            message_count=1,
            latest_at=datetime(2026, 4, 27, 9, 0, 0),
            has_schedule=False,
        ),
    ],
    "hr@company.com": [
        ThreadSummary(
            thread_id="d4c3b2a1f0e9d8c7",
            subject="복리후생 안내",
            status="참고",
            summary_preview="2분기 복리후생 변경사항 공지",
            message_count=1,
            latest_at=datetime(2026, 4, 26, 14, 20, 0),
            has_schedule=False,
        ),
    ],
}

THREADS: dict[str, ThreadDetail] = {
    "a3f9b2c1d4e5f6a7": ThreadDetail(
        thread_id="a3f9b2c1d4e5f6a7",
        subject="프로젝트 일정 논의",
        status="회신 필요",
        summary="프로젝트 기획안 검토 후 다음 주 미팅 일정 확정 요청. 첨부된 문서 검토 필요.",
        schedules=[
            Schedule(
                text="다음 주 화요일 오후 3시",
                parsed=datetime(2026, 5, 5, 15, 0, 0),
            ),
        ],
        messages=[
            MessageDetail(
                message_id="INBOX:1234",
                from_="boss@company.com",
                from_name="김부장",
                to=["me@example.com"],
                date=datetime(2026, 4, 28, 10, 30, 0),
                body=(
                    "안녕하세요. 첨부한 기획안 검토 부탁드립니다. "
                    "다음 주 화요일 오후 3시에 미팅 잡으면 어떨까요?"
                ),
                attachments=[
                    Attachment(idx=0, filename="기획안.pdf", size=102400),
                ],
            ),
        ],
    ),
    "b2e8a1d0c3f4e5b6": ThreadDetail(
        thread_id="b2e8a1d0c3f4e5b6",
        subject="주간 리포트",
        status="완료",
        summary="이번 주 진행 상황 보고 완료",
        schedules=[],
        messages=[
            MessageDetail(
                message_id="INBOX:1230",
                from_="boss@company.com",
                from_name="김부장",
                to=["me@example.com"],
                date=datetime(2026, 4, 25, 17, 0, 0),
                body="이번 주 리포트 잘 받았습니다. 감사합니다.",
                attachments=[],
            ),
        ],
    ),
    "c1d7e6f5a4b3c2d1": ThreadDetail(
        thread_id="c1d7e6f5a4b3c2d1",
        subject="이번 주의 AI 뉴스",
        status="참고",
        summary="LLM 최신 동향과 오픈소스 모델 업데이트 소식 정리",
        schedules=[],
        messages=[
            MessageDetail(
                message_id="INBOX:1228",
                from_="newsletter@tech.com",
                from_name="Tech Weekly",
                to=["me@example.com"],
                date=datetime(2026, 4, 27, 9, 0, 0),
                body="이번 주 주요 AI 소식을 모았습니다...",
                attachments=[],
            ),
        ],
    ),
    "d4c3b2a1f0e9d8c7": ThreadDetail(
        thread_id="d4c3b2a1f0e9d8c7",
        subject="복리후생 안내",
        status="참고",
        summary="2분기 복리후생 변경사항 공지",
        schedules=[],
        messages=[
            MessageDetail(
                message_id="INBOX:1225",
                from_="hr@company.com",
                from_name="인사팀",
                to=["me@example.com"],
                date=datetime(2026, 4, 26, 14, 20, 0),
                body="2분기부터 적용되는 복리후생 변경사항을 안내드립니다...",
                attachments=[
                    Attachment(idx=0, filename="복리후생_안내.pdf", size=51200),
                ],
            ),
        ],
    ),
}
