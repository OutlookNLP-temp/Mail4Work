# Mail4Work API 명세

FastAPI 백엔드와 Streamlit 프론트엔드 간의 계약 문서.

- **Base URL:** `http://localhost:8000`
- **Content-Type:** `application/json`
- **인증:** 없음 (로컬 단독 실행)

---

## 엔드포인트 목록

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/sync` | IMAP에서 새 메일 가져오기 |
| `GET` | `/sync/status` | 마지막 동기화 시각 / 진행 여부 |
| `GET` | `/senders` | 발신자 그룹 리스트 |
| `GET` | `/senders/{sender_id}/threads` | 한 발신자의 스레드 목록 |
| `GET` | `/threads/{thread_id}` | 스레드 상세 (메시지 + 요약 + 일정) |
| `GET` | `/messages/{message_id}/attachments/{idx}` | 첨부파일 다운로드 (bytes) |

---

## ID 체계

| ID | 형식 | 예시 |
|---|---|---|
| `sender_id` | 이메일 주소 | `boss@company.com` |
| `thread_id` | 헤더 기반 hash (16자) | `a3f9b2c1d4e5f6a7` |
| `message_id` | `{folder}:{IMAP_UID}` | `INBOX:1234` |

URL에 들어갈 때 `sender_id`는 URL 인코딩 필요 (`@` → `%40`).

---

## 1. `POST /sync`

IMAP 서버에서 새 메일을 가져와 SQLite 캐시에 저장한다.

**Request Body:** 없음

**Response 200:**
```json
{
  "fetched": 12,
  "total": 348,
  "started_at": "2026-04-28T10:30:00",
  "finished_at": "2026-04-28T10:30:08"
}
```

---

## 2. `GET /sync/status`

**Response 200:**
```json
{
  "last_sync_at": "2026-04-28T10:30:08",
  "in_progress": false,
  "total_messages": 348
}
```

---

## 3. `GET /senders`

발신자별로 그룹화된 리스트. 최근 메일 시각 내림차순.

**Query params:**
- `limit` (int, default=50)
- `offset` (int, default=0)

**Response 200:**
```json
[
  {
    "sender_id": "boss@company.com",
    "name": "김부장",
    "email": "boss@company.com",
    "thread_count": 12,
    "unread_count": 3,
    "latest_at": "2026-04-28T10:30:00"
  }
]
```

---

## 4. `GET /senders/{sender_id}/threads`

한 발신자의 스레드 목록. 최신순.

**Query params:**
- `limit` (int, default=50)
- `offset` (int, default=0)

**Response 200:**
```json
[
  {
    "thread_id": "a3f9b2c1d4e5f6a7",
    "subject": "프로젝트 일정 논의",
    "status": "회신 필요",
    "summary_preview": "프로젝트 기획안 검토 후 다음 주 미팅 일정 확정 요청",
    "message_count": 4,
    "latest_at": "2026-04-28T10:30:00",
    "has_schedule": true
  }
]
```

`status` 값: `"회신 필요" | "진행 중" | "완료" | "참고"`

---

## 5. `GET /threads/{thread_id}`

스레드 전체 상세. 메시지는 시간순(오래된 → 최신).

**Response 200:**
```json
{
  "thread_id": "a3f9b2c1d4e5f6a7",
  "subject": "프로젝트 일정 논의",
  "status": "회신 필요",
  "summary": "프로젝트 기획안 검토 후 다음 주 미팅 일정 확정 요청. 첨부된 문서 검토 필요.",
  "schedules": [
    {
      "text": "다음 주 화요일 오후 3시",
      "parsed": "2026-05-05T15:00:00"
    }
  ],
  "messages": [
    {
      "message_id": "INBOX:1234",
      "from": "boss@company.com",
      "from_name": "김부장",
      "to": ["me@example.com"],
      "date": "2026-04-28T10:30:00",
      "body": "...",
      "attachments": [
        {"idx": 0, "filename": "기획안.pdf", "size": 102400}
      ]
    }
  ]
}
```

---

## 6. `GET /messages/{message_id}/attachments/{idx}`

첨부파일 raw bytes 반환.

**Response 200:**
- `Content-Type: application/octet-stream`
- `Content-Disposition: attachment; filename="기획안.pdf"`
- Body: 파일 바이트

---

## 디자인 결정 사항

1. **요약 트리거:** Lazy + SQLite 캐시. 처음 `/threads/{id}` 호출 시 KoBART 추론, 이후 캐시 반환.
2. **동기화:** 사용자 명시적 트리거(`POST /sync`). 자동 polling 없음.
3. **상태 수정:** MVP는 자동 분류 결과만 (읽기 전용). 수동 변경은 추후.
4. **본문/첨부 fetch:** Lazy. `/threads/{id}` 호출 시 IMAP에서 본문 가져와 캐시.
5. **에러:** 표준 HTTP 상태 코드 + `{"detail": "..."}` 형태.

---

## 변경 시 규칙

API 명세 변경은 양쪽 작업에 영향 → **수정 전 반드시 팀원과 합의**.
