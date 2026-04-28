# Mail4Work

메일 데이터 기반 업무 자동화 서비스

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # 값 채우기
```

### Ollama (요약 모델)

요약은 로컬 Ollama로 EXAONE 3.5 2.4B를 호출한다.

```bash
brew install ollama          # macOS
ollama serve &               # 백그라운드 데몬
ollama pull exaone3.5:2.4b   # 1.5GB 다운로드 (1회)
```

## Run

```bash
# IMAP 동기화 (설정된 폴더의 새 메일을 SQLite에 적재)
python -m src.mail.fetch

# 백엔드 (FastAPI, 포트 8000)
uvicorn src.api.main:app --reload

# 프론트 (Streamlit, 포트 8501)
streamlit run src/ui/mail.py
```

## Structure

```
src/
├── mail/        # IMAP fetch, 발신자 그룹화, 스레드 묶기
├── analyze/     # EXAONE 요약, 한국어 일정 추출, 키워드 상태 분류
├── db/          # SQLite 스키마, 캐시
├── api/         # FastAPI 엔드포인트
└── ui/          # Streamlit 앱
```

## Stack

- **Mail**: IMAP (`imap-tools`)
- **Summarize**: EXAONE 3.5 2.4B via Ollama
- **Schedule extract**: 정규식 + 자체 한국어 날짜 파서
- **Status classify**: 키워드 룰
- **Backend**: FastAPI
- **Frontend**: Streamlit
- **Cache**: SQLite
