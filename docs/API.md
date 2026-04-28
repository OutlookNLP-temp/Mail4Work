# Mail4Work API 명세

FastAPI 백엔드와 Streamlit 프론트엔드 간의 계약 문서.

- **Base URL:** `http://localhost:8000`
- **Content-Type:** `application/json`
- **인증:** 없음 (로컬 단독 실행)

---

## 엔드포인트 목록

| Method | Path | 설명 |
|---|---|---|
| `POST` | `/sync` | 설정된 폴더에서 새 메일 가져오기 |
| `GET` | `/sync/status` | 마지막 동기화 시각 / 진행 여부 |
| `GET` | `/senders` | 컨택트(자기 자신 제외) 리스트 |
| `GET` | `/senders/{sender_id}/messages` | 컨택트와 주고받은 메시지 + 통계 |
| `GET` | `/senders/{sender_id}/threads` | 컨택트의 스레드 목록 (스레드 뷰용) |
| `GET` | `/threads/{thread_id}` | 스레드 상세 (메시지 + 요약 + 일정) |
| `GET` | `/messages/{message_id}/attachments/{idx}` | 첨부파일 다운로드 |

---

## ID 체계 / 환경변수

| 항목 | 형식/값 | 예시 |
|---|---|---|
| `sender_id` | 이메일 주소 (URL 인코딩 필요) | `boss%40company.com` |
| `thread_id` | 헤더 기반 SHA1 해시 (16자) | `a3f9b2c1d4e5f6a7` |
| `message_id` | `{folder}:{IMAP_UID}` | `INBOX:1234` |
| `ME_EMAIL` (env) | "나"로 식별할 이메일. 비우면 `IMAP_USER` 사용 | `me@example.com` |
| `IMAP_FOLDERS` (env) | 동기화할 폴더 콤마 구분 | `INBOX,Sent` |

---

## 1. `POST /sync`

설정된 모든 폴더(`IMAP_FOLDERS`)에서 새 메일을 가져와 SQLite에 저장하고, 스레드 그룹을 재계산한다.

**Response 200:**
```json
{
  "fetched": 12,
  "per_folder": {"INBOX": 8, "Sent": 4},
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

컨택트(주고받은 상대) 리스트. **`ME_EMAIL`은 결과에서 제외.** 최신 메일 시각 내림차순.

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
    "message_count": 12,
    "latest_at": "2026-04-28T10:30:00"
  }
]
```

---

## 4. `GET /senders/{sender_id}/messages`

컨택트와 주고받은 모든 메시지(받은 + 보낸)를 시간순(오래된 → 최신)으로 반환. 메시지마다 KoBART 요약과 direction이 포함된다.

**Query params:**
- `limit` (int, default=200)
- `offset` (int, default=0)

**Response 200:**
```json
{
  "stats": {
    "total": 12,
    "sent": 5,
    "received": 7
  },
  "messages": [
    {
      "message_id": "INBOX:1234",
      "direction": "received",
      "from": "boss@company.com",
      "from_name": "김부장",
      "date": "2026-04-28T10:30:00",
      "subject": "프로젝트 일정 논의",
      "summary": "기획안 검토 후 다음 주 미팅 일정 확정 요청.",
      "body": "...",
      "attachments": []
    },
    {
      "message_id": "Sent:520",
      "direction": "sent",
      "from": "me@example.com",
      "from_name": "나",
      "date": "2026-04-28T11:00:00",
      "subject": "Re: 프로젝트 일정 논의",
      "summary": "다음 주 화요일 오후 3시에 가능합니다.",
      "body": "...",
      "attachments": []
    }
  ]
}
```

`direction` 값: `"sent" | "received"`

---

## 5. `GET /senders/{sender_id}/threads`

컨택트가 참여한 스레드 목록. **현재 UI 미사용**이지만 추후 Thread View 화면 추가를 위해 유지.

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
    "summary_preview": "기획안 검토 후 다음 주 미팅 일정 확정 요청.",
    "message_count": 4,
    "latest_at": "2026-04-28T10:30:00",
    "has_schedule": true
  }
]
```

`status` 값: `"회신 필요" | "진행 중" | "완료" | "참고"`

---

## 6. `GET /threads/{thread_id}`

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
      "attachments": []
    }
  ]
}
```

---

## 7. `GET /messages/{message_id}/attachments/{idx}`

첨부파일 raw bytes 반환.

**Response 200:**
- `Content-Type: application/octet-stream`
- `Content-Disposition: attachment; filename="기획안.pdf"`
- Body: 파일 바이트

---

## 디자인 결정

1. **요약 트리거:** Lazy + SQLite 캐시. 메시지 단위(`/senders/{id}/messages`)에서 KoBART 추론, 결과는 `summaries` 테이블에 저장. 다음 호출부터 캐시 반환.
2. **동기화:** 사용자 명시적 트리거(`POST /sync`). 자동 polling 없음.
3. **본문/첨부 fetch:** 본문은 sync 시 같이 저장. 첨부 다운로드는 별도 엔드포인트.
4. **컨택트 그룹화:** `from_email = me`이면 첫 `to_email`을 컨택트로, 아니면 `from_email`을 컨택트로. `me_email` 자체는 컨택트 리스트에서 제외.
5. **에러:** 표준 HTTP 상태 코드 + `{"detail": "..."}` 형태.
