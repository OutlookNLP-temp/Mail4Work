import os

import httpx

# Ollama 로컬 LLM 엔드포인트와 사용 모델 (env로 오버라이드 가능)
_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_MODEL = os.getenv("SUMMARIZER_MODEL", "exaone3.5:2.4b")

# 짧은 메일은 그냥 원문 보여주는 게 더 유용
_MIN_INPUT_CHARS = 100

_PROMPT = """다음은 한국어 메일 본문입니다. 핵심 내용만 2-3문장 이내로 한국어로 요약해 주세요. 인사말과 마무리 인사말은 빼고, 누가 무엇을 요청했는지/공유했는지가 드러나게 해 주세요.

[메일 본문]
{body}

[요약]"""


def summarize(text: str, timeout: float = 120.0) -> str:
    """EXAONE(Ollama)로 한국어 메일 본문을 요약한다."""
    # 빈 입력 가드
    if not text or not text.strip():
        return ""

    # 너무 짧으면 모델 거치지 않고 원문 반환
    body = text.strip()
    if len(body) < _MIN_INPUT_CHARS:
        return body

    # Ollama generate API 호출
    try:
        r = httpx.post(
            f"{_OLLAMA_HOST}/api/generate",
            json={
                "model": _MODEL,
                "prompt": _PROMPT.format(body=body),
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 200,
                },
            },
            timeout=timeout,
        )
        r.raise_for_status()
    except httpx.HTTPError:
        # Ollama 미실행 또는 모델 미설치 → 원문 앞부분으로 fallback
        return body[:200]

    return (r.json().get("response") or "").strip()


def main():
    sample = (
        "안녕하세요. 개발팀 정수민 매니저입니다. "
        "결제 모듈 리팩토링 PR 올렸습니다. "
        "주요 변경은 인터페이스 분리와 테스트 커버리지 보강입니다. "
        "내일 오후 3시까지 리뷰 부탁드릴 수 있을까요?"
    )
    print("입력:", sample)
    print()
    print("요약:", summarize(sample))


if __name__ == "__main__":
    main()
