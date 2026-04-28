# Mail4Work

메일 데이터 기반 업무 자동화 서비스

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 값 채우기
```

## Run

```bash
# IMAP 연결 확인 (최근 메일 10개 출력)
python -m src.mail.fetch

# 백엔드 (FastAPI)
uvicorn src.api.main:app --reload

# 프론트 (Streamlit)
streamlit run src/ui/app.py
```

## Structure

```
src/
├── mail/        # IMAP fetch, 발신자 그룹화, 스레드 묶기
├── analyze/     # KoBART 요약, dateparser 일정 추출, 키워드 분류
├── db/          # SQLite 스키마, 캐시
├── api/         # FastAPI 엔드포인트
└── ui/          # Streamlit 앱
```

## Stack

- **Mail**: IMAP (`imap-tools`)
- **Summarize**: KoBART (`gogamza/kobart-summarization`)
- **Schedule extract**: `dateparser` + 정규식
- **Status classify**: 키워드 룰
- **Backend**: FastAPI
- **Frontend**: Streamlit
- **Cache**: SQLite
