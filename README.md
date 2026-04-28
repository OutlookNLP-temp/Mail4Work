# Mail4Work

IMAP으로 메일을 가져와 데이터 기반 업무 자동화를 실험하는 짧은 프로젝트.

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
