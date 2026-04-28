from dataclasses import dataclass

# 우선순위 순서: 위에 있을수록 먼저 매칭. 액션이 필요한 상태가 우선.
_RULES: list[tuple[str, list[str]]] = [
    (
        "회신 필요",
        [
            "회신",
            "답변 부탁",
            "확인 부탁",
            "검토 부탁",
            "검토해주",
            "확인해주",
            "알려주세요",
            "알려주실",
            "여쭙",
            "여쭤",
            "문의",
            "?",
            "?",
        ],
    ),
    (
        "진행 중",
        [
            "진행 중",
            "진행중",
            "작업 중",
            "검토 중",
            "처리 중",
            "확인 중",
            "준비 중",
        ],
    ),
    (
        "완료",
        [
            "완료했",
            "처리 완료",
            "확인 완료",
            "잘 받았",
            "잘 받았습니다",
            "수고하셨",
            "고생하셨",
        ],
    ),
]

DEFAULT_STATUS = "참고"


@dataclass
class Classification:
    status: str
    matched_keyword: str | None


def classify(text: str) -> Classification:
    """본문 키워드를 매칭해 상태(회신 필요/진행 중/완료/참고) 반환."""
    # 빈 입력은 참고로
    if not text or not text.strip():
        return Classification(status=DEFAULT_STATUS, matched_keyword=None)

    # 우선순위대로 키워드 매칭
    for status, keywords in _RULES:
        for kw in keywords:
            if kw in text:
                return Classification(status=status, matched_keyword=kw)

    # 어디에도 안 걸리면 참고
    return Classification(status=DEFAULT_STATUS, matched_keyword=None)


def main():
    samples = [
        "기획안 검토 부탁드립니다. 회신 기다리겠습니다.",
        "다음 주 화요일 오후 3시에 미팅 잡으면 어떨까요?",
        "현재 진행 중이며 금주 내로 마무리하겠습니다.",
        "보고서 잘 받았습니다. 감사합니다.",
        "처리 완료했습니다.",
        "이번 주 사내 행사 안내드립니다. 자세한 내용은 첨부 참고하세요.",
        "확인 부탁드립니다. 결과 알려주세요.",
        "수고하셨습니다.",
    ]
    for s in samples:
        c = classify(s)
        print(f"[{c.status}] (matched: {c.matched_keyword!r}) - {s}")


if __name__ == "__main__":
    main()
