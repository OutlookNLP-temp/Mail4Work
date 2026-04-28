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
python -m src.fetch_mail
```

## Structure

```
src/            # 코드
.env.example    # IMAP 접속 정보 템플릿
requirements.txt
```
