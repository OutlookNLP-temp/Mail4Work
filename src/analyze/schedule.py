import re
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class ExtractedSchedule:
    text: str
    parsed: datetime


_WEEKDAY = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

# 결합형부터 우선 매칭 (긴 패턴이 짧은 패턴 영역을 선점)
_PATTERNS = [
    # 다음/이번/차주 + 요일 + 오전/오후 N시 (M분)?
    re.compile(
        r"(?:다음|이번|차)\s*주\s*[월화수목금토일]요일\s*"
        r"(?:오전|오후)\s*\d{1,2}시(?:\s*\d{1,2}분)?"
    ),
    # 내일/모레/글피 + 오전/오후 N시
    re.compile(
        r"(?:내일|모레|글피)\s*(?:오전|오후)\s*\d{1,2}시(?:\s*\d{1,2}분)?"
    ),
    # N월 N일 + 오전/오후 N시
    re.compile(
        r"\d{1,2}월\s*\d{1,2}일\s*(?:오전|오후)\s*\d{1,2}시(?:\s*\d{1,2}분)?"
    ),
    # 다음/이번/차주 + 요일
    re.compile(r"(?:다음|이번|차)\s*주\s*[월화수목금토일]요일"),
    # N월 N일
    re.compile(r"\d{1,2}월\s*\d{1,2}일"),
    # 내일/모레/글피/오늘
    re.compile(r"내일|모레|글피|오늘"),
    # 오전/오후 N시 (M분)?
    re.compile(r"(?:오전|오후)\s*\d{1,2}시(?:\s*\d{1,2}분)?"),
]


def extract_schedules(
    text: str, base: datetime | None = None
) -> list[ExtractedSchedule]:
    """본문에서 한국어 날짜/시간 표현을 추출해 datetime으로 파싱한다."""
    # 빈 입력 가드
    if not text or not text.strip():
        return []

    base = base or datetime.now()
    # 이미 더 긴 패턴이 잡은 영역 — 짧은 패턴이 중복 매칭하는 것 방지
    occupied: list[tuple[int, int]] = []
    found: list[ExtractedSchedule] = []

    for pattern in _PATTERNS:
        for m in pattern.finditer(text):
            # 선점된 영역과 겹치면 건너뜀
            if any(s <= m.start() < e or s < m.end() <= e for s, e in occupied):
                continue
            phrase = m.group().strip()
            parsed = _parse_phrase(phrase, base)
            if parsed is None:
                continue
            found.append(ExtractedSchedule(text=phrase, parsed=parsed))
            occupied.append((m.start(), m.end()))

    # 등장 순서 유지하면서 (text, parsed) 중복 제거
    seen: set[tuple[str, datetime]] = set()
    unique: list[ExtractedSchedule] = []
    for s in found:
        key = (s.text, s.parsed)
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)
    return unique


def _parse_phrase(phrase: str, base: datetime) -> datetime | None:
    # 시간 부분(오전/오후 N시 M분) 분리
    hour, minute = None, None
    time_m = re.search(
        r"(오전|오후)\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", phrase
    )
    if time_m:
        ampm, hh, mm = time_m.groups()
        # 12시는 그대로, 그 외는 0~11로 정규화 후 오후면 +12
        hour = int(hh) % 12
        if ampm == "오후":
            hour += 12
        minute = int(mm) if mm else 0
        phrase = phrase[: time_m.start()].strip()

    # 날짜 부분 파싱
    date = _parse_date_part(phrase, base)

    if date is None:
        # 시간만 있는 경우 base 날짜의 그 시간으로
        if hour is not None:
            return base.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        return None

    # 날짜 + 시간 (시간 없으면 오전 9시 기본값)
    if hour is not None:
        return date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return date.replace(hour=9, minute=0, second=0, microsecond=0)


def _parse_date_part(phrase: str, base: datetime) -> datetime | None:
    if not phrase:
        return None

    # 다음/이번/차주 + X요일
    m = re.match(r"(다음|이번|차)\s*주\s*([월화수목금토일])요일$", phrase)
    if m:
        prefix, wd_char = m.group(1), m.group(2)
        target = _WEEKDAY[wd_char]
        # 이번 주 기준 같은 요일까지의 일수 (0~6)
        days = (target - base.weekday()) % 7
        # 다음 주/차주는 일주일 더 (단, 같은 요일이면 +7만)
        if prefix in ("다음", "차"):
            days = days + 7 if days != 0 else 7
        return _date_only(base) + timedelta(days=days)

    # N월 N일 — 과거면 내년으로
    m = re.match(r"(\d{1,2})월\s*(\d{1,2})일$", phrase)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        try:
            d = datetime(base.year, month, day)
        except ValueError:
            return None
        if d.date() < base.date():
            try:
                d = datetime(base.year + 1, month, day)
            except ValueError:
                return None
        return d

    # 내일/모레/글피/오늘
    if phrase == "오늘":
        return _date_only(base)
    if phrase == "내일":
        return _date_only(base) + timedelta(days=1)
    if phrase == "모레":
        return _date_only(base) + timedelta(days=2)
    if phrase == "글피":
        return _date_only(base) + timedelta(days=3)

    return None


def _date_only(d: datetime) -> datetime:
    # 시/분/초/마이크로초 0으로 초기화
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def main():
    base = datetime(2026, 4, 28, 13, 0)  # 화요일
    samples = [
        "다음 주 화요일 오후 3시에 미팅 잡으면 어떨까요?",
        "차주 수요일까지 검토 부탁드립니다.",
        "5월 6일 오전 10시 30분에 보내드리겠습니다.",
        "내일 오후 2시 회의 예정입니다.",
        "오늘 안에 회신 부탁드립니다.",
        "이번 주 금요일까지요.",
        "12월 25일 휴무 안내",
        "모레 오전 9시까지 부탁",
    ]
    for s in samples:
        print(f"\n[{s}]")
        for r in extract_schedules(s, base=base):
            print(f"  - text='{r.text}', parsed={r.parsed.isoformat()}")


if __name__ == "__main__":
    main()
