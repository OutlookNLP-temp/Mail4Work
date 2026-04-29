import os
import re

import httpx

# Ollama 로컬 LLM 엔드포인트와 사용 모델 (env로 오버라이드 가능)
_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_MODEL = os.getenv("SUMMARIZER_MODEL", "exaone3.5:2.4b")

# 짧은 메일은 그냥 원문 보여주는 게 더 유용
_MIN_INPUT_CHARS = 100

_PROMPT = """다음은 한국어 메일 본문입니다. 핵심만 압축한 짧은 요약을 만들어 주세요.
규칙:
- 1~2문장, 합쳐서 100자 이내로 만들어 주세요.
- 인사말과 마무리 인사말은 빼주세요.
- 본문에 없는 내용은 절대 추가하지 마세요. 본문에서 직접 확인되는 사실만 요약하세요.
- 부연 설명, 의도 추측, 일반적인 결론(예: "도움이 될 것입니다") 같은 추가 문장은 넣지 마세요.
- "요약:" 같은 머리말이나 마크다운(**, ##) 없이 본문만 출력하세요.
- {subject_rule}

[메일 본문]
{body}

[요약]"""

# 본문 전처리 — 토큰 낭비 줄여 핵심 본문이 모델 어텐션에 더 많이 잡히게
_QUOTED_RE = re.compile(r"^\s*>.*$", re.MULTILINE)  # 인용부 (>>>...)
_SIGNATURE_RE = re.compile(r"\n--\s*\n.*$", re.DOTALL)  # 표준 서명 구분자 이후
_BLANK_RUN_RE = re.compile(r"\n{3,}")  # 3개 이상 빈 줄 → 2개로

# 출력 후처리 — 모델이 가끔 흘리는 메타 헤더/감싸기 정리
_SUMMARY_HEADER_RE = re.compile(
    r"^\s*(?:\*+\s*요약\s*[:：]?\s*\*+|#+\s*요약\s*[:：]?|요약\s*[:：]|\[요약\])\s*\n+",
)

# 인사말/마무리 인사 — 짧은 메일에서 LLM 거치지 않을 때 떼기
_GREETING_RE = re.compile(
    r"^\s*(?:안녕하세요|안녕하십니까|안녕하셨어요|안녕|반갑습니다|"
    r"고생하십니다|고생하셨습니다|수고하십니다)[\s.,!~ㅎㅋ]*",
)
_CLOSING_RE = re.compile(
    r"\s*(?:감사합니다|감사드립니다|수고하세요|수고하십시오|"
    r"부탁드립니다|잘\s*부탁드립니다)[.!\s]*$",
)


def _preprocess(body: str) -> str:
    # CRLF 정규화 + 인용부/서명 제거 + 빈 줄 압축
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    body = _QUOTED_RE.sub("", body)
    body = _SIGNATURE_RE.sub("", body)
    body = _BLANK_RUN_RE.sub("\n\n", body)
    return body.strip()


def _strip_greetings(body: str) -> str:
    # 본문 양 끝의 인사말/마무리 인사 제거 (짧은 메일 그대로 출력 시 사용)
    body = _GREETING_RE.sub("", body)
    body = _CLOSING_RE.sub("", body)
    return body.strip()


def _post_process(text: str) -> str:
    # LLM 출력에서 메타 헤더 제거
    return _SUMMARY_HEADER_RE.sub("", text.strip()).strip()


def _subject_rule(direction: str, sender_name: str | None) -> str:
    # 발신자/방향 컨텍스트를 프롬프트에 주입해 "팀원 A" 같은 일반화 방지
    if direction == "sent":
        return (
            "이 메일은 사용자 본인이 보낸 메일입니다. 본인이 한 행동/요청은 "
            "주어를 '본인은'으로 쓰거나 1인칭(요청했다, 공유했다)으로 서술하세요. "
            "절대 '팀원 A', '팀장', '담당자' 같은 가공의 직책/인물명을 만들지 마세요. "
            "본문에 직책이 명시되어 있지 않으면 직책을 추측해서 붙이지 마세요."
        )
    sender = (sender_name or "").strip()
    if sender:
        return (
            f"이 메일은 '{sender}'(으)로부터 받은 메일입니다. 발신자의 행동은 "
            f"주어를 '{sender}'로 서술하세요. '팀원 A', '팀장', '담당자' 같은 "
            "가공의 직책/인물명을 만들지 마세요."
        )
    return (
        "누가 무엇을 요청했는지/공유했는지가 드러나게 하되, "
        "'팀원 A', '팀장', '담당자' 같은 가공의 직책/인물명은 만들지 마세요."
    )


def summarize(
    text: str,
    sender_name: str | None = None,
    direction: str = "received",
    timeout: float = 120.0,
) -> str:
    """EXAONE(Ollama)로 한국어 메일 본문을 요약한다."""
    # 빈 입력 가드
    if not text or not text.strip():
        return ""

    # 전처리 후 길이 재판정 — 짧으면 원문에서 인사말만 떼고 반환
    body = _preprocess(text)
    if len(body) < _MIN_INPUT_CHARS:
        return _strip_greetings(body)

    # Ollama generate API 호출
    prompt = _PROMPT.format(subject_rule=_subject_rule(direction, sender_name), body=body)
    try:
        r = httpx.post(
            f"{_OLLAMA_HOST}/api/generate",
            json={
                "model": _MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    # 한국어 토큰 기준 2-3문장이 잘리지 않게 여유 있게
                    "num_predict": 500,
                },
            },
            timeout=timeout,
        )
        r.raise_for_status()
    except httpx.HTTPError:
        # Ollama 미실행 또는 모델 미설치 → 원문 앞부분으로 fallback
        return body[:200]

    raw = _post_process(r.json().get("response") or "")
    return _split_paragraphs(raw)


def _split_paragraphs(text: str) -> str:
    # 문장 단위로 분리 + 짧은 문장은 다음 문장과 묶어 단락 단위로 정렬
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    if not parts:
        return ""

    # 짧은 문장(<= 35자)은 다음 문장과 같은 단락으로 합쳐서 한 줄로
    paragraphs: list[str] = []
    buf = ""
    for sent in parts:
        if buf:
            buf = f"{buf} {sent}"
        else:
            buf = sent
        # 문장 길이가 충분히 크고 단락 끝나면 flush
        if len(buf) >= 36:
            paragraphs.append(buf)
            buf = ""
    if buf:
        # 마지막 잔여 — 직전 단락이 있으면 합치고 아니면 단독
        if paragraphs:
            paragraphs[-1] = f"{paragraphs[-1]} {buf}"
        else:
            paragraphs.append(buf)

    # 단락 사이는 빈 줄로 — 시각적 가독성
    return "\n\n".join(paragraphs)


def warmup(timeout: float = 30.0) -> bool:
    """모델을 메모리에 미리 올려 첫 요청 콜드 스타트(약 2~3초) 회피."""
    try:
        httpx.post(
            f"{_OLLAMA_HOST}/api/generate",
            json={
                "model": _MODEL,
                "prompt": "ok",
                "stream": False,
                "options": {"num_predict": 1},
            },
            timeout=timeout,
        ).raise_for_status()
        return True
    except httpx.HTTPError:
        return False


def main():
    sample = (
        "안녕하세요. 개발팀 정수민 매니저입니다. "
        "결제 모듈 리팩토링 PR 올렸습니다. "
        "주요 변경은 인터페이스 분리와 테스트 커버리지 보강입니다. "
        "내일 오후 3시까지 리뷰 부탁드릴 수 있을까요? 감사합니다."
    )
    print("입력:", sample)
    print()
    print("요약:", summarize(sample))


if __name__ == "__main__":
    main()
