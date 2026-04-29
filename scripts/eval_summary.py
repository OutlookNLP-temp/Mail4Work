"""요약 성능 벤치마크 — 품질 메트릭 + 환각 탐지 + 지연 측정.

실행:
    .venv/bin/python -m scripts.eval_summary [--with-latency]

전제:
    - data/mail4work.db 에 messages + summaries 가 채워져 있어야 함
    - --with-latency 시 Ollama 데몬 + 요약 모델이 떠 있어야 함
"""
import argparse
import re
import sqlite3
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "mail4work.db"

# 출력 시 잡고 싶은 패턴들
_FAKE_NAMES = ("팀장", "팀원 A", "팀원 B", "팀원A", "팀원B", "담당자", "직원 A", "책임자")
_MD_HEADER_RE = re.compile(r"\*\*요약|\[요약\]|^#+\s*요약|^요약\s*[:：]", re.MULTILINE)
_GREET_START_RE = re.compile(r"^\s*(안녕하세요|안녕하십니까|안녕!|반갑습니다)")
_CLOSING_END_RE = re.compile(r"(감사합니다|수고하세요|수고하십시오)\.?\s*$")

# 환각 탐지용 — 본문/요약에서 후보 토큰 추출
_NUM_RE = re.compile(r"\d+")
# 3자 이상 대문자 시작 — re.ASCII로 \b가 한글-영문 경계 인식하게
_ENG_PROPER_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b", re.ASCII)
# 5글자 이상 한글 토큰만 — 4자는 조사/활용형이 섞여 false positive 많음
_KOR_KW_RE = re.compile(r"[가-힣]{5,}")

# 압축률 평가에서 짧은 메일은 제외 (LLM 미경유)
_LONG_BODY_THRESHOLD = 100


def _kw_partial_in(kw: str, body: str) -> bool:
    # 한국어 조사/활용/보조용언 흡수 — 끝 1~3자 떼며 prefix 매칭
    # 어근이 본문에 있으면 OK (e.g. "계획입니다" → "계획")
    if kw in body:
        return True
    n = len(kw)
    for trim in range(1, min(4, n - 1)):
        if kw[: n - trim] in body:
            return True
    return False


def _hallucination(summary: str, body: str, allowlist: set[str]) -> dict:
    """요약에 있지만 본문에 없는 토큰들을 찾아 반환.

    한글 키워드는 조사/활용형 차이를 흡수해 prefix 매칭까지 허용.
    allowlist 는 발신자명/수신자명 등 메타에서 알려진 정상 토큰.
    """
    s_nums = set(_NUM_RE.findall(summary))
    b_nums = set(_NUM_RE.findall(body))
    s_eng = set(_ENG_PROPER_RE.findall(summary))
    b_eng = set(_ENG_PROPER_RE.findall(body))
    s_kw = set(_KOR_KW_RE.findall(summary))

    missing_korean = []
    for kw in sorted(s_kw):
        if kw in allowlist:
            continue
        if _kw_partial_in(kw, body):
            continue
        # 발신자명 변형 흡수 (예: "주희정은" → 발신자 "주희정"이 allowlist면 통과)
        if any(name and name in kw for name in allowlist):
            continue
        missing_korean.append(kw)

    return {
        "missing_numbers": sorted(s_nums - b_nums),
        "missing_english": sorted(s_eng - b_eng),
        "missing_korean": missing_korean,
    }


def _direction(folder: str | None) -> str:
    folder = folder or ""
    return "sent" if "Sent" in folder or "보낸" in folder else "received"


def evaluate_quality(rows: list[sqlite3.Row]) -> dict:
    long_rows = [r for r in rows if r["body"] and len(r["body"]) >= _LONG_BODY_THRESHOLD]
    sent_rows = [r for r in rows if _direction(r["folder"]) == "sent"]
    recv_long = [
        r for r in long_rows if _direction(r["folder"]) == "received"
    ]

    metrics = {
        "n_total": len(rows),
        "n_sent": len(sent_rows),
        "n_recv_long": len(recv_long),
        "n_long": len(long_rows),
    }

    # 부정 메트릭
    metrics["fake_name"] = sum(
        1 for r in rows if any(name in r["summary"] for name in _FAKE_NAMES)
    )
    metrics["md_header"] = sum(1 for r in rows if _MD_HEADER_RE.search(r["summary"]))
    metrics["greet_start"] = sum(1 for r in rows if _GREET_START_RE.match(r["summary"]))
    metrics["closing_end"] = sum(1 for r in rows if _CLOSING_END_RE.search(r["summary"]))
    metrics["crlf"] = sum(1 for r in rows if "\r" in r["summary"])

    # 톤 통일 — 모든 문장이 합쇼체("~다.", "~까?")로 끝나는지
    # LLM 거치는 긴 메일만 측정 (짧은 메일은 원문 그대로)
    # 숫자 사이 마침표("2.0") 는 문장 구분으로 보지 않게 lookahead 사용
    sent_split_re = re.compile(r"[.!?](?=\s+[^\d]|\s*$)")
    honorific_violations = 0
    for r in long_rows:
        sentences = [s.strip() for s in sent_split_re.split(r["summary"]) if s.strip()]
        if not sentences:
            continue
        # 합쇼체 종결: 마지막 한글이 '다'/'까'/'죠'/'네'
        all_honorific = all(
            re.search(r"[가-힣]*(다|까|죠|네)$", s) for s in sentences
        )
        if not all_honorific:
            honorific_violations += 1
    metrics["tone_violations"] = honorific_violations

    # 긍정 메트릭
    metrics["sent_first_person"] = sum(
        1 for r in sent_rows
        if "본인" in r["summary"]
        or re.search(r"(요청했|공유했|문의드렸|드렸)", r["summary"])
    )
    metrics["recv_named"] = sum(
        1 for r in recv_long if r["from_name"] and r["from_name"] in r["summary"]
    )

    # 통계
    if long_rows:
        metrics["avg_compression"] = sum(
            len(r["summary"]) / len(r["body"]) for r in long_rows
        ) / len(long_rows)
        metrics["avg_paragraphs"] = sum(
            r["summary"].count("\n\n") + 1 for r in long_rows
        ) / len(long_rows)
    else:
        metrics["avg_compression"] = 0
        metrics["avg_paragraphs"] = 0
    metrics["avg_summary_len"] = (
        sum(len(r["summary"]) for r in rows) // len(rows) if rows else 0
    )

    return metrics


def evaluate_hallucination(rows: list[sqlite3.Row]) -> dict:
    """본문에 없는 토큰이 요약에 등장한 케이스 집계."""
    halluc_summary = {
        "n_with_missing_number": 0,
        "n_with_missing_english": 0,
        "n_with_missing_korean": 0,
        "samples": [],
    }
    for r in rows:
        if not r["body"]:
            continue
        # 발신자명 + 본인 / 사용자 등 허용 토큰
        allowlist = {"본인", "사용자"}
        if r["from_name"]:
            allowlist.add(r["from_name"])
        h = _hallucination(r["summary"], r["body"], allowlist)
        if h["missing_numbers"]:
            halluc_summary["n_with_missing_number"] += 1
        if h["missing_english"]:
            halluc_summary["n_with_missing_english"] += 1
        if h["missing_korean"]:
            halluc_summary["n_with_missing_korean"] += 1
        if h["missing_numbers"] or h["missing_english"] or h["missing_korean"]:
            halluc_summary["samples"].append(
                {
                    "subject": (r["subject"] or "")[:40],
                    "from": r["from_name"] or r["from_email"],
                    "missing": h,
                }
            )
    return halluc_summary


def measure_latency(rows: list[sqlite3.Row], repeats: int = 3) -> dict:
    """summarize.summarize() 직접 호출 시간 분포."""
    sys.path.insert(0, str(ROOT))
    from src.analyze.summarize import summarize

    samples = [r for r in rows if r["body"] and len(r["body"]) >= _LONG_BODY_THRESHOLD][
        :5
    ]
    times = []
    for r in samples:
        for _ in range(repeats):
            t0 = time.time()
            _ = summarize(
                r["body"],
                sender_name=r["from_name"],
                direction=_direction(r["folder"]),
            )
            times.append(time.time() - t0)
    if not times:
        return {"n": 0}
    return {
        "n": len(times),
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "p95": sorted(times)[int(len(times) * 0.95)],
        "min": min(times),
        "max": max(times),
    }


def _pct(num: int, total: int) -> str:
    return f"{num}/{total} ({100 * num / total:.0f}%)" if total else "n/a"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-latency",
        action="store_true",
        help="LLM 직접 호출 시간 분포까지 측정 (Ollama 떠 있어야 함)",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT m.message_id, m.folder, m.from_email, m.from_name,
               m.subject, m.body, s.summary
        FROM messages m JOIN summaries s ON s.message_id = m.message_id
        """
    ).fetchall()

    if not rows:
        print("⚠️  summaries 비어있음. UI에서 메시지 한 번 조회해 lazy 트리거 후 재실행.")
        return

    print("=" * 60)
    print("📊 요약 품질 메트릭")
    print("=" * 60)
    q = evaluate_quality(rows)
    print(f"데이터셋: {q['n_total']}건 (sent {q['n_sent']}, 긴 메일 {q['n_long']})")
    print()
    print("부정 메트릭 (낮을수록 좋음)")
    print(f"  가공 인물명          : {_pct(q['fake_name'], q['n_total'])}")
    print(f"  마크다운 헤더        : {_pct(q['md_header'], q['n_total'])}")
    print(f"  시작 인사말 잔존     : {_pct(q['greet_start'], q['n_total'])}")
    print(f"  끝 인사 잔존         : {_pct(q['closing_end'], q['n_total'])}")
    print(f"  CRLF 잔존            : {_pct(q['crlf'], q['n_total'])}")
    print(f"  톤 비통일 (명사컷 등): {_pct(q['tone_violations'], q['n_long'])}")
    print()
    print("긍정 메트릭 (높을수록 좋음)")
    print(f"  sent 1인칭 사용      : {_pct(q['sent_first_person'], q['n_sent'])}")
    print(f"  recv 발신자명 등장   : {_pct(q['recv_named'], q['n_recv_long'])}")
    print()
    print("통계")
    print(f"  평균 압축률          : {q['avg_compression']:.2f}")
    print(f"  평균 단락 수         : {q['avg_paragraphs']:.1f}")
    print(f"  평균 요약 길이       : {q['avg_summary_len']}자")

    print()
    print("=" * 60)
    print("🔍 환각 자동 탐지 (lexical)")
    print("=" * 60)
    h = evaluate_hallucination(rows)
    # 강한 신호 — 본문에 없는 숫자/영문 고유명사는 paraphrasing 변동이 작음
    print("강한 신호 (낮을수록 좋음)")
    print(f"  본문에 없는 숫자 등장 : {_pct(h['n_with_missing_number'], q['n_total'])}")
    print(f"  본문에 없는 영문 등장 : {_pct(h['n_with_missing_english'], q['n_total'])}")
    # 약한 신호 — 한국어 활용/paraphrasing 흡수 한계로 false positive 多
    print()
    print("약한 신호 (paraphrasing 흡수 못 해 false positive 가능)")
    print(f"  본문에 없는 한글 키워드: {_pct(h['n_with_missing_korean'], q['n_total'])}")
    if h["samples"]:
        # 강한 신호가 잡힌 케이스만 의심 출력 — 한글-only는 노이즈라 생략
        strong = [
            s for s in h["samples"]
            if s["missing"]["missing_numbers"] or s["missing"]["missing_english"]
        ]
        if strong:
            print()
            print("강한 의심 케이스:")
            for s in strong[:5]:
                miss = s["missing"]
                parts = []
                if miss["missing_numbers"]:
                    parts.append(f"숫자={miss['missing_numbers']}")
                if miss["missing_english"]:
                    parts.append(f"영문={miss['missing_english']}")
                print(f"  - [{s['from']}] {s['subject']}")
                print(f"      {' / '.join(parts)}")
        else:
            print()
            print("✅ 강한 신호 환각 케이스 없음")

    if args.with_latency:
        print()
        print("=" * 60)
        print("⏱️  지연 (LLM 직접 호출, 5건 × 3회)")
        print("=" * 60)
        lat = measure_latency(rows)
        if lat["n"]:
            print(f"  n={lat['n']}")
            print(f"  평균   : {lat['mean']:.2f}s")
            print(f"  중앙값 : {lat['median']:.2f}s")
            print(f"  p95    : {lat['p95']:.2f}s")
            print(f"  최대   : {lat['max']:.2f}s")
            print(f"  최소   : {lat['min']:.2f}s")


if __name__ == "__main__":
    main()
