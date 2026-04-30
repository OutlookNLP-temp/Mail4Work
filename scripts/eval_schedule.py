"""한국어 일정 추출 정확도 벤치마크 — 라벨링 기반 precision/recall/F1.

실행:
    .venv/bin/python -m scripts.eval_schedule

기준 시각:
    2026-04-28 13:00 (화요일) — 위키의 적용 전후 표와 동일.
"""
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.analyze.schedule import extract_schedules

# 라벨링 기준 시각 — 화요일로 고정해 요일/상대 표현 결과 재현 가능
BASE = datetime(2026, 4, 28, 13, 0)


# 패턴 카테고리:
#   weekday_time     : 다음/이번/차주 + 요일 + 시간
#   weekday          : 다음/이번/차주 + 요일
#   month_day_time   : N월 N일 + 시간
#   month_day        : N월 N일
#   relative_time    : 내일/모레/글피 + 시간
#   relative         : 내일/모레/글피/오늘
#   time_only        : 오전/오후 N시 (단독)
#   multi            : 여러 일정 동시 등장
#   negative         : 일정 표현 없음 (false positive 검출)
#   limitation       : 코드가 미지원하는 것으로 알려진 표현 (한계 가시화용)
DATASET = [
    # ── weekday_time (8건) ────────────────────────────────────────────
    {
        "input": "다음 주 화요일 오후 3시에 미팅 잡으면 어떨까요?",
        "expected": [("다음 주 화요일 오후 3시", "2026-05-05T15:00:00")],
        "category": "weekday_time",
    },
    {
        "input": "차주 수요일 오전 10시까지 회신 부탁드립니다.",
        "expected": [("차주 수요일 오전 10시", "2026-05-06T10:00:00")],
        "category": "weekday_time",
    },
    {
        "input": "이번 주 금요일 오후 2시 회의 예정입니다.",
        "expected": [("이번 주 금요일 오후 2시", "2026-05-01T14:00:00")],
        "category": "weekday_time",
    },
    {
        "input": "다음 주 월요일 오전 11시 30분에 보고드리겠습니다.",
        "expected": [("다음 주 월요일 오전 11시 30분", "2026-05-11T11:30:00")],
        "category": "weekday_time",
    },
    {
        "input": "차주 목요일 오후 5시까지 검토 마치겠습니다.",
        "expected": [("차주 목요일 오후 5시", "2026-05-07T17:00:00")],
        "category": "weekday_time",
    },
    {
        "input": "이번 주 수요일 오전 9시 스탠드업 합니다.",
        "expected": [("이번 주 수요일 오전 9시", "2026-04-29T09:00:00")],
        "category": "weekday_time",
    },
    {
        "input": "다음 주 금요일 오후 6시 회식 어떠세요?",
        "expected": [("다음 주 금요일 오후 6시", "2026-05-08T18:00:00")],
        "category": "weekday_time",
    },
    {
        "input": "차주 화요일 오전 10시 15분에 발표 시작합니다.",
        "expected": [("차주 화요일 오전 10시 15분", "2026-05-05T10:15:00")],
        "category": "weekday_time",
    },

    # ── weekday (6건) ─────────────────────────────────────────────────
    {
        "input": "이번 주 금요일까지 보내주세요.",
        "expected": [("이번 주 금요일", "2026-05-01T09:00:00")],
        "category": "weekday",
    },
    {
        "input": "차주 수요일까지 검토 부탁드립니다.",
        "expected": [("차주 수요일", "2026-05-06T09:00:00")],
        "category": "weekday",
    },
    {
        "input": "다음 주 목요일 마감입니다.",
        "expected": [("다음 주 목요일", "2026-05-07T09:00:00")],
        "category": "weekday",
    },
    {
        "input": "이번 주 토요일 행사 있습니다.",
        "expected": [("이번 주 토요일", "2026-05-02T09:00:00")],
        "category": "weekday",
    },
    {
        "input": "차주 금요일 발표가 잡혔어요.",
        "expected": [("차주 금요일", "2026-05-08T09:00:00")],
        "category": "weekday",
    },
    {
        "input": "다음 주 일요일 가능하신지요?",
        "expected": [("다음 주 일요일", "2026-05-10T09:00:00")],
        "category": "weekday",
    },

    # ── month_day_time (6건) ──────────────────────────────────────────
    {
        "input": "5월 6일 오전 10시 30분에 보내드리겠습니다.",
        "expected": [("5월 6일 오전 10시 30분", "2026-05-06T10:30:00")],
        "category": "month_day_time",
    },
    {
        "input": "6월 15일 오후 2시 본사 미팅입니다.",
        "expected": [("6월 15일 오후 2시", "2026-06-15T14:00:00")],
        "category": "month_day_time",
    },
    {
        "input": "12월 31일 오후 11시 59분 마감 처리 예정입니다.",
        "expected": [("12월 31일 오후 11시 59분", "2026-12-31T23:59:00")],
        "category": "month_day_time",
    },
    {
        "input": "5월 1일 오전 9시 발송하겠습니다.",
        "expected": [("5월 1일 오전 9시", "2026-05-01T09:00:00")],
        "category": "month_day_time",
    },
    {
        "input": "9월 10일 오후 3시 45분 화상 미팅 잡았습니다.",
        "expected": [("9월 10일 오후 3시 45분", "2026-09-10T15:45:00")],
        "category": "month_day_time",
    },
    {
        "input": "11월 11일 오후 1시 행사 일정 공유드립니다.",
        "expected": [("11월 11일 오후 1시", "2026-11-11T13:00:00")],
        "category": "month_day_time",
    },

    # ── month_day (5건) ───────────────────────────────────────────────
    {
        "input": "12월 25일 휴무 안내드립니다.",
        "expected": [("12월 25일", "2026-12-25T09:00:00")],
        "category": "month_day",
    },
    {
        "input": "5월 5일 어린이날 휴무입니다.",
        "expected": [("5월 5일", "2026-05-05T09:00:00")],
        "category": "month_day",
    },
    {
        "input": "8월 15일 임시 공휴일 안내합니다.",
        "expected": [("8월 15일", "2026-08-15T09:00:00")],
        "category": "month_day",
    },
    {
        "input": "10월 9일 한글날 사내 행사 진행됩니다.",
        "expected": [("10월 9일", "2026-10-09T09:00:00")],
        "category": "month_day",
    },
    {
        # base(4/28)보다 과거 날짜 → 코드는 내년으로 해석
        "input": "4월 1일 만우절 이벤트 안내드립니다.",
        "expected": [("4월 1일", "2027-04-01T09:00:00")],
        "category": "month_day",
    },

    # ── relative_time (6건) ───────────────────────────────────────────
    {
        "input": "내일 오후 2시 회의 예정입니다.",
        "expected": [("내일 오후 2시", "2026-04-29T14:00:00")],
        "category": "relative_time",
    },
    {
        "input": "모레 오전 9시까지 부탁드립니다.",
        "expected": [("모레 오전 9시", "2026-04-30T09:00:00")],
        "category": "relative_time",
    },
    {
        "input": "글피 오후 5시 미팅 잡혔습니다.",
        "expected": [("글피 오후 5시", "2026-05-01T17:00:00")],
        "category": "relative_time",
    },
    {
        "input": "내일 오전 11시 30분에 자료 공유드리겠습니다.",
        "expected": [("내일 오전 11시 30분", "2026-04-29T11:30:00")],
        "category": "relative_time",
    },
    {
        "input": "모레 오후 4시까지 답변드리겠습니다.",
        "expected": [("모레 오후 4시", "2026-04-30T16:00:00")],
        "category": "relative_time",
    },
    {
        "input": "글피 오전 10시 출장 출발입니다.",
        "expected": [("글피 오전 10시", "2026-05-01T10:00:00")],
        "category": "relative_time",
    },

    # ── relative (5건) ────────────────────────────────────────────────
    {
        "input": "오늘 안에 회신 부탁드립니다.",
        "expected": [("오늘", "2026-04-28T09:00:00")],
        "category": "relative",
    },
    {
        "input": "내일 보고서 제출하겠습니다.",
        "expected": [("내일", "2026-04-29T09:00:00")],
        "category": "relative",
    },
    {
        "input": "모레까지 끝내겠습니다.",
        "expected": [("모레", "2026-04-30T09:00:00")],
        "category": "relative",
    },
    {
        "input": "글피 회의 잡혔어요.",
        "expected": [("글피", "2026-05-01T09:00:00")],
        "category": "relative",
    },
    {
        "input": "오늘 점심 같이 어떠세요?",
        "expected": [("오늘", "2026-04-28T09:00:00")],
        "category": "relative",
    },

    # ── time_only (4건) ───────────────────────────────────────────────
    {
        "input": "오후 3시에 회의실 A에서 봅시다.",
        "expected": [("오후 3시", "2026-04-28T15:00:00")],
        "category": "time_only",
    },
    {
        "input": "오전 10시까지 도착하겠습니다.",
        "expected": [("오전 10시", "2026-04-28T10:00:00")],
        "category": "time_only",
    },
    {
        "input": "오후 6시 30분에 끝납니다.",
        "expected": [("오후 6시 30분", "2026-04-28T18:30:00")],
        "category": "time_only",
    },
    {
        "input": "오전 11시 미팅 시작합니다.",
        "expected": [("오전 11시", "2026-04-28T11:00:00")],
        "category": "time_only",
    },

    # ── multi (4건) ───────────────────────────────────────────────────
    {
        "input": "내일 오후 2시 / 모레 오전 9시 두 차례 미팅입니다.",
        "expected": [
            ("내일 오후 2시", "2026-04-29T14:00:00"),
            ("모레 오전 9시", "2026-04-30T09:00:00"),
        ],
        "category": "multi",
    },
    {
        "input": "5월 6일 오전 10시 회의 후 5월 7일 오후 3시 보고드리겠습니다.",
        "expected": [
            ("5월 6일 오전 10시", "2026-05-06T10:00:00"),
            ("5월 7일 오후 3시", "2026-05-07T15:00:00"),
        ],
        "category": "multi",
    },
    {
        "input": "내일까지 자료 보내주시면 모레 검토하겠습니다.",
        "expected": [
            ("내일", "2026-04-29T09:00:00"),
            ("모레", "2026-04-30T09:00:00"),
        ],
        "category": "multi",
    },
    {
        "input": "다음 주 화요일 오후 3시 또는 다음 주 수요일 오후 4시 가능하신가요?",
        "expected": [
            ("다음 주 화요일 오후 3시", "2026-05-05T15:00:00"),
            ("다음 주 수요일 오후 4시", "2026-05-06T16:00:00"),
        ],
        "category": "multi",
    },

    # ── negative (6건) — 일정 표현 없음 ────────────────────────────────
    {
        "input": "안녕하세요 잘 지내시죠?",
        "expected": [],
        "category": "negative",
    },
    {
        "input": "검토 완료했습니다.",
        "expected": [],
        "category": "negative",
    },
    {
        "input": "확인 부탁드립니다.",
        "expected": [],
        "category": "negative",
    },
    {
        "input": "보고서 잘 받았습니다. 감사합니다.",
        "expected": [],
        "category": "negative",
    },
    {
        "input": "프로젝트 진행 중입니다.",
        "expected": [],
        "category": "negative",
    },
    {
        "input": "수고하셨습니다.",
        "expected": [],
        "category": "negative",
    },

    # ── limitation (4건) — 코드 미지원 패턴, recall 한계 가시화용 ────────
    {
        # ISO 절대 날짜 — 정규식 패턴에 미포함
        "input": "2026-05-06 회의 일정 공유드립니다.",
        "expected": [("2026-05-06", "2026-05-06T09:00:00")],
        "category": "limitation",
    },
    {
        # 슬래시 날짜 표기 — 정규식 패턴에 미포함
        "input": "5/6 점심 회의 잡혔습니다.",
        "expected": [("5/6", "2026-05-06T09:00:00")],
        "category": "limitation",
    },
    {
        # "다음 달" 표현 — 코드는 "N월 N일" 절대 표기만 인식
        "input": "다음 달 6일까지 자료 부탁드립니다.",
        "expected": [("다음 달 6일", "2026-05-06T09:00:00")],
        "category": "limitation",
    },
    {
        # "내주" 표현 — 코드는 "다음/이번/차" 접두사만 인식
        "input": "내주 화요일 미팅 가능하신가요?",
        "expected": [("내주 화요일", "2026-05-05T09:00:00")],
        "category": "limitation",
    },
]


def evaluate_case(case: dict) -> dict:
    """단일 케이스 추출 결과를 라벨과 비교해 TP/FP/FN 산출."""
    predicted = extract_schedules(case["input"], base=BASE)
    pred_set = {(p.text, p.parsed.isoformat()) for p in predicted}
    exp_set = {(t, p) for t, p in case["expected"]}

    return {
        "input": case["input"],
        "category": case["category"],
        "tp": pred_set & exp_set,
        "fp": pred_set - exp_set,
        "fn": exp_set - pred_set,
    }


def metrics(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    # P/R/F1 — 분모 0인 경우 0 반환
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return p, r, f1


def _fmt(p: float, r: float, f1: float) -> str:
    return f"P={p:.2f} R={r:.2f} F1={f1:.2f}"


def main():
    results = [evaluate_case(c) for c in DATASET]

    # 전체 집계
    total_tp = sum(len(r["tp"]) for r in results)
    total_fp = sum(len(r["fp"]) for r in results)
    total_fn = sum(len(r["fn"]) for r in results)

    print("=" * 60)
    print(f"📅 한국어 일정 추출 정확도 (n={len(DATASET)})")
    print(f"   기준 시각: {BASE.strftime('%Y-%m-%d %H:%M')} (화요일)")
    print("=" * 60)
    p, r, f1 = metrics(total_tp, total_fp, total_fn)
    print(
        f"전체  : {_fmt(p, r, f1)}  "
        f"(TP={total_tp} FP={total_fp} FN={total_fn})"
    )
    print()

    # 카테고리별 집계
    by_cat: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in results:
        by_cat[r["category"]][0] += len(r["tp"])
        by_cat[r["category"]][1] += len(r["fp"])
        by_cat[r["category"]][2] += len(r["fn"])

    print("카테고리별:")
    cat_order = [
        "weekday_time", "weekday",
        "month_day_time", "month_day",
        "relative_time", "relative",
        "time_only", "multi", "negative", "limitation",
    ]
    for cat in cat_order:
        if cat not in by_cat:
            continue
        tp_, fp_, fn_ = by_cat[cat]
        if cat == "negative":
            # negative 는 P/R 정의가 어색해 FP만 표기
            print(f"  {cat:<16}: FP={fp_}")
        else:
            p_, r_, f1_ = metrics(tp_, fp_, fn_)
            print(
                f"  {cat:<16}: {_fmt(p_, r_, f1_)}  "
                f"(TP={tp_} FP={fp_} FN={fn_})"
            )

    # 실패 케이스 (FP/FN 있는 것만)
    failures = [r for r in results if r["fp"] or r["fn"]]
    if failures:
        print()
        print("실패 케이스:")
        for r in failures:
            print(f"  [{r['category']}] {r['input']}")
            for fp in sorted(r["fp"]):
                print(f"      FP: {fp}")
            for fn in sorted(r["fn"]):
                print(f"      FN: {fn}")
    else:
        print()
        print("✅ 실패 케이스 없음")


if __name__ == "__main__":
    main()
