from functools import lru_cache

from transformers import BartForConditionalGeneration, PreTrainedTokenizerFast

MODEL_NAME = "gogamza/kobart-summarization"
_MAX_INPUT_TOKENS = 1024
_MIN_INPUT_CHARS = 100


@lru_cache(maxsize=1)
def _load_model() -> tuple[PreTrainedTokenizerFast, BartForConditionalGeneration]:
    # 모델 1회만 로드해 메모리에 캐시
    tokenizer = PreTrainedTokenizerFast.from_pretrained(MODEL_NAME)
    model = BartForConditionalGeneration.from_pretrained(MODEL_NAME)
    # 추론 전용 모드
    model.eval()
    return tokenizer, model


def summarize(text: str, max_length: int = 128, num_beams: int = 4) -> str:
    """KoBART로 한국어 텍스트를 요약한다.

    1024 토큰 초과분은 잘라내고 요약한다.
    """
    # 빈 입력 가드
    if not text or not text.strip():
        return ""

    # 본문이 너무 짧으면 요약 의미 없고 모델 출력도 망가짐 → 원문 반환
    if len(text.strip()) < _MIN_INPUT_CHARS:
        return text.strip()

    tokenizer, model = _load_model()

    # 토크나이즈 + 1024 토큰 초과분 잘라내기
    inputs = tokenizer(
        text,
        max_length=_MAX_INPUT_TOKENS,
        truncation=True,
        return_tensors="pt",
    )

    # 빔 서치로 요약 생성 (3-gram 반복 방지)
    summary_ids = model.generate(
        inputs["input_ids"],
        num_beams=num_beams,
        max_length=max_length,
        no_repeat_ngram_size=3,
        early_stopping=True,
    )

    # 토큰 → 텍스트 디코딩 (특수 토큰 제외)
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()


def main():
    sample = (
        "안녕하세요. 다음 주 월요일에 예정된 프로젝트 미팅 일정을 확정하고자 합니다. "
        "지난번 논의된 기획안에 대한 검토 의견을 정리해서 첨부 파일로 보냅니다. "
        "특히 3장 일정 부분과 5장 예산 부분은 추가 논의가 필요할 것 같습니다. "
        "검토 후 회신 부탁드립니다. 감사합니다."
    )
    print("입력 길이:", len(sample), "자")
    print("요약:", summarize(sample))


if __name__ == "__main__":
    main()
