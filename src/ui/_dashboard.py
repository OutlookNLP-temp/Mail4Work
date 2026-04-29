from collections import Counter
from datetime import datetime, timedelta
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from _api import (
    fetch_messages,
    fetch_senders,
    fetch_sync_status,
    render_sync_button,
)

_STATUS_COLORS = {
    "회신 필요": "#ff9800",
    "진행 중": "#2196f3",
    "완료": "#4caf50",
    "참고": "#9e9e9e",
}

# 대시보드 전용 스타일 (상단에서 1회 주입)
_CSS = """
<style>
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin: 8px 0 22px 0;
}
.kpi-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 22px 24px;
    border: 2px solid #e9ecf0;
}
.kpi-head {
    font-size: 13px;
    color: #5a6478;
    font-weight: 500;
    margin-bottom: 16px;
}
.kpi-value {
    font-size: 36px;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1;
    margin-bottom: 14px;
}
.kpi-value.orange { color: #f0863d; }
.kpi-value.blue   { color: #4a8df0; }
.kpi-sub {
    font-size: 12px;
    color: #9ba3b3;
}

/* 섹션 단위 컨테이너 카드 */
.section-card {
    background: #ffffff;
    border: 2px solid #e9ecf0;
    border-radius: 16px;
    padding: 20px 24px;
    margin-bottom: 16px;
}
.section-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}
.section-title { font-size: 16px; font-weight: 700; color: #1a1a1a; }

/* 필터 pill (정적, 시각용) */
.filter-pills { display: flex; gap: 6px; }
.filter-pill {
    padding: 5px 14px;
    border-radius: 999px;
    font-size: 12px;
    color: #5a6478;
    background: #f5f7fa;
}
.filter-pill.active { background: #e3f2fd; color: #1976d2; }

/* 회신 필요 행 — 아바타 + 본문 */
.reply-row {
    display: flex;
    gap: 14px;
    padding: 14px 0;
    border-bottom: 1px dashed #e9ecf0;
}
.reply-row:last-child { border-bottom: none; padding-bottom: 0; }
.reply-row:first-of-type { padding-top: 0; }
.avatar {
    width: 40px;
    height: 40px;
    min-width: 40px;
    border-radius: 50%;
    background: #e3f2fd;
    color: #1976d2;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 600;
    font-size: 14px;
}
.reply-content { flex: 1; min-width: 0; }
.reply-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
    gap: 8px;
}
.reply-name-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.reply-name { font-weight: 700; color: #1a1a1a; font-size: 14px; }
.reply-time { font-size: 12px; color: #9ba3b3; white-space: nowrap; }
.reply-text { font-size: 13px; color: #444; line-height: 1.55; }
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 500;
}
.badge.orange { background: #fff3e0; color: #f0863d; }

/* 일정 행 — 날짜 박스 + 본문 */
.sched-row {
    display: flex;
    gap: 14px;
    padding: 12px 0;
    border-bottom: 1px dashed #e9ecf0;
    align-items: center;
}
.sched-row:last-child { border-bottom: none; padding-bottom: 0; }
.sched-row:first-of-type { padding-top: 0; }
.sched-date {
    background: #eef3ff;
    border-radius: 8px;
    padding: 8px 10px;
    text-align: center;
    min-width: 58px;
}
.sched-date.urgent { background: #fff3e0; }
.sched-day   { font-size: 18px; font-weight: 700; color: #4f6df0; line-height: 1.1; }
.sched-month { font-size: 10px; color: #4f6df0; text-transform: uppercase; letter-spacing: 0.5px; }
.sched-date.urgent .sched-day,
.sched-date.urgent .sched-month { color: #f0863d; }
.sched-time  { font-size: 11px; color: #777; margin-top: 4px; }
.sched-content { flex: 1; min-width: 0; }
.sched-title { font-weight: 600; font-size: 14px; color: #1a1a1a; }
.sched-meta  { font-size: 12px; color: #777; margin-top: 4px; }

/* 컨택트 활동 히트맵 */
.heatmap-row {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 10px 0;
    border-bottom: 1px dashed #e9ecf0;
}
.heatmap-row:last-child { border-bottom: none; }
.heatmap-row:first-of-type { padding-top: 0; }
.heatmap-name { width: 110px; font-size: 13px; color: #1a1a1a; font-weight: 500; }
.heatmap-cells { display: flex; gap: 4px; flex: 1; }
.heatmap-cell {
    width: 26px;
    height: 22px;
    border-radius: 4px;
    background: #f0f4fa;
    flex-shrink: 0;
}
.heatmap-cell.i1 { background: #d8e6fa; }
.heatmap-cell.i2 { background: #a9caf3; }
.heatmap-cell.i3 { background: #6ea6ec; }
.heatmap-cell.i4 { background: #3a7ddc; }
.heatmap-total { font-weight: 700; color: #1a1a1a; min-width: 30px; text-align: right; font-size: 14px; }
.section-meta { font-size: 12px; color: #9ba3b3; }

/* 도넛 + 범례 */
.donut-wrap {
    display: flex;
    align-items: center;
    gap: 28px;
    margin: 6px 0;
}
.donut-svg { flex-shrink: 0; }
.donut-legend { display: flex; flex-direction: column; gap: 12px; flex: 1; }
.legend-row { display: flex; align-items: center; gap: 10px; font-size: 14px; }
.legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.legend-label { color: #5a6478; flex: 1; }
.legend-pct { font-weight: 700; color: #1a1a1a; }

/* 상단 헤더 */
.header-wrap {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin: 8px 0 24px 0;
    gap: 16px;
}
.header-title { font-size: 30px; font-weight: 700; color: #1a1a1a; line-height: 1.2; }
.header-sub   { font-size: 14px; color: #5a6478; margin-top: 8px; }
.header-right { text-align: right; padding-top: 8px; min-width: 220px; }
.header-stat  { font-size: 13px; color: #9ba3b3; margin-bottom: 4px; }

.insight-card {
    background: #f3f7ff;
    padding: 14px 18px;
    border-radius: 8px;
    color: #2c3e64;
    font-size: 13px;
    margin-top: 10px;
}
</style>
"""


def _greeting() -> str:
    h = datetime.now().hour
    if h < 12:
        return "좋은 아침이에요 👋"
    if h < 18:
        return "오후도 화이팅 ☕"
    return "마무리 시간이네요 🌙"


def _naive(dt_str: str) -> datetime:
    # API에서 오는 ISO 8601이 timezone 있을 수 있어 naive로 정규화
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _kpi_card(icon: str, label: str, value: int, value_color: str = "", sub: str = "") -> str:
    # 라벨/아이콘 상단 → 큰 숫자 중간 → 서브 하단 구조
    return (
        '<div class="kpi-card">'
        f'<div class="kpi-head">{icon} {escape(label)}</div>'
        f'<div class="kpi-value {value_color}">{value}</div>'
        f'<div class="kpi-sub">{escape(sub)}</div>'
        "</div>"
    )


def _avatar_char(name: str) -> str:
    name = (name or "?").strip()
    return name[:1].upper() if name[:1].isascii() else name[:1]


def _relative_time(dt: datetime) -> str:
    now = datetime.now()
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    if dt >= today:
        return dt.strftime("%H:%M")
    if dt >= yesterday:
        return "어제"
    days = (today.date() - dt.date()).days
    return f"{days}일 전"


def _reply_row(name: str, dt: datetime, body: str) -> str:
    # 한 줄 요약: 본문 첫 문단만 잘라 표시 (길면 ellipsis)
    snippet = body.replace("\n\n", " · ").replace("\n", " ")
    if len(snippet) > 160:
        snippet = snippet[:160] + "..."
    return (
        '<div class="reply-row">'
        f'<div class="avatar">{escape(_avatar_char(name))}</div>'
        '<div class="reply-content">'
        '<div class="reply-head">'
        '<div class="reply-name-row">'
        f'<span class="reply-name">{escape(name)}</span>'
        '<span class="badge orange">회신 필요</span>'
        "</div>"
        f'<div class="reply-time">{escape(_relative_time(dt))}</div>'
        "</div>"
        f'<div class="reply-text">{escape(snippet)}</div>'
        "</div>"
        "</div>"
    )


def _heatmap_intensity(count: int) -> str:
    # 일별 메일 수에 따라 4단계 색 강도
    if count == 0:
        return ""
    if count == 1:
        return "i1"
    if count <= 3:
        return "i2"
    if count <= 5:
        return "i3"
    return "i4"


def _heatmap_row(name: str, counts: list[int], total: int) -> str:
    cells = "".join(
        f'<div class="heatmap-cell {_heatmap_intensity(c)}" title="{c}건"></div>'
        for c in counts
    )
    return (
        '<div class="heatmap-row">'
        f'<div class="heatmap-name">{escape(name)}</div>'
        f'<div class="heatmap-cells">{cells}</div>'
        f'<div class="heatmap-total">{total}</div>'
        "</div>"
    )


def _donut_svg(slices: list[tuple[str, int, str]], total: int) -> str:
    # 도넛 SVG — stroke-dasharray로 각 조각 그리기
    cx, cy, r = 60, 60, 38
    sw = 18
    circ = 2 * 3.141592653589793 * r
    parts: list[str] = []
    offset = 0.0
    for _label, count, color in slices:
        if count <= 0 or total <= 0:
            continue
        seg = count / total * circ
        gap = circ - seg
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-dasharray="{seg:.2f} {gap:.2f}" '
            f'stroke-dashoffset="{-offset:.2f}" '
            f'transform="rotate(-90 {cx} {cy})" />'
        )
        offset += seg
    return (
        '<svg viewBox="0 0 120 120" width="180" height="180" class="donut">'
        + "".join(parts)
        + "</svg>"
    )


def _legend_row(label: str, color: str, pct: float) -> str:
    return (
        '<div class="legend-row">'
        f'<span class="legend-dot" style="background:{color}"></span>'
        f'<span class="legend-label">{escape(label)}</span>'
        f'<span class="legend-pct">{pct:.0f}%</span>'
        "</div>"
    )


def _sched_row(parsed: datetime, sched_text: str, subject: str, sender: str, urgent: bool = False) -> str:
    # 마감까지 24시간 이내 → 주황 강조
    date_cls = "sched-date urgent" if urgent else "sched-date"
    return (
        '<div class="sched-row">'
        f'<div class="{date_cls}">'
        f'<div class="sched-day">{parsed.strftime("%d")}</div>'
        f'<div class="sched-month">{parsed.strftime("%b")}</div>'
        f'<div class="sched-time">{parsed.strftime("%H:%M")}</div>'
        "</div>"
        '<div class="sched-content">'
        f'<div class="sched-title">{escape(subject)}</div>'
        f'<div class="sched-meta">{escape(sched_text)} · {escape(sender)}</div>'
        "</div>"
        "</div>"
    )


# ─── 페이지 시작 ──────────────────────────────────────────────────────────
st.markdown(_CSS, unsafe_allow_html=True)

st.sidebar.title("📬 Mail4Work")
render_sync_button()

# 데이터 로드
try:
    sync_status = fetch_sync_status()
    senders = fetch_senders()
except Exception as e:
    st.error(f"API 연결 실패: {e}")
    st.stop()

if not senders:
    st.info("아직 메일이 없습니다. 사이드바의 동기화를 실행하세요.")
    st.stop()

# 모든 컨택트의 메시지 수집 (캐시되어 있어 가벼움)
all_messages: list[dict] = []
with st.spinner("데이터 집계 중..."):
    for s in senders:
        try:
            payload = fetch_messages(s["email"])
        except Exception:
            continue
        for m in payload["messages"]:
            m["sender_email"] = s["email"]
            m["sender_display"] = s.get("name") or s["email"]
            all_messages.append(m)

# ─── 헤더 ────────────────────────────────────────────────────────────────
_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]
now = datetime.now()
last = sync_status.get("last_sync_at")
last_str = datetime.fromisoformat(last).strftime("%H:%M") if last else "-"
date_full = f"{now.year}년 {now.month}월 {now.day}일 {_WEEKDAYS[now.weekday()]}요일"
total_mails = sync_status.get("total_messages", 0)

# 회신 필요 카운트는 KPI 계산 직전에 미리 한 번 빼서 sub에 활용
_pre_needs_reply = sum(1 for m in all_messages if m.get("status") == "회신 필요")
hint = (
    f"오늘은 회신 {_pre_needs_reply}건이 기다리고 있어요"
    if _pre_needs_reply
    else "회신할 메일이 없어요 🎉"
)

st.markdown(
    f'<div class="header-wrap">'
    '<div class="header-left">'
    f'<div class="header-title">{_greeting()}</div>'
    f'<div class="header-sub">{escape(date_full)} · {escape(hint)}</div>'
    "</div>"
    '<div class="header-right">'
    f'<div class="header-stat">총 {total_mails}건 · {len(senders)}명의 컨택트</div>'
    f'<div class="header-stat">마지막 동기화 {escape(last_str)}</div>'
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)

# ─── KPI 카드 4개 ─────────────────────────────────────────────────────────
needs_reply = [m for m in all_messages if m.get("status") == "회신 필요"]
in_progress = [m for m in all_messages if m.get("status") == "진행 중"]

week_end = now + timedelta(days=7)
week_schedules: list[tuple[datetime, dict, dict]] = []
for m in all_messages:
    for s in m.get("schedules", []):
        parsed = datetime.fromisoformat(s["parsed"])
        # 이미 지난 시각은 제외 (now 이후 ~ 7일 이내)
        if now <= parsed <= week_end:
            week_schedules.append((parsed, s, m))

since_24h = now - timedelta(hours=24)
new_24h = [m for m in all_messages if _naive(m["date"]) >= since_24h]
new_24h_sent = sum(1 for m in new_24h if m.get("direction") == "sent")
new_24h_recv = len(new_24h) - new_24h_sent

# KPI 서브 텍스트 계산
today_start = datetime(now.year, now.month, now.day)
yesterday_start = today_start - timedelta(days=1)
today_reply = sum(1 for m in needs_reply if _naive(m["date"]) >= today_start)
yesterday_reply = sum(
    1 for m in needs_reply
    if yesterday_start <= _naive(m["date"]) < today_start
)
reply_diff = today_reply - yesterday_reply

in_progress_senders = {m["sender_email"] for m in in_progress}

tomorrow_start = today_start + timedelta(days=1)
tomorrow_end = tomorrow_start + timedelta(days=1)
tomorrow_schedules = sum(
    1 for parsed, _, _ in week_schedules
    if tomorrow_start <= parsed < tomorrow_end
)

reply_sub = (
    f"어제 대비 {'+' if reply_diff >= 0 else ''}{reply_diff}"
    if (today_reply or yesterday_reply)
    else "신규 없음"
)
progress_sub = (
    f"{len(in_progress_senders)}명과의 스레드" if in_progress_senders else "스레드 없음"
)
schedule_sub = (
    f"{tomorrow_schedules}건은 내일" if tomorrow_schedules else "내일 일정 없음"
)
new_sub = f"받음 {new_24h_recv} · 보냄 {new_24h_sent}"

kpi_html = (
    '<div class="kpi-grid">'
    + _kpi_card("📨", "회신 필요", len(needs_reply), "orange", reply_sub)
    + _kpi_card("🚧", "진행 중", len(in_progress), "", progress_sub)
    + _kpi_card("📅", "이번 주 일정", len(week_schedules), "blue", schedule_sub)
    + _kpi_card("✉️", "신규 (24H)", len(new_24h), "", new_sub)
    + "</div>"
)
st.markdown(kpi_html, unsafe_allow_html=True)

# ─── 회신 필요 + 다가오는 일정 ────────────────────────────────────────────
c1, c2 = st.columns(2)

with c1:
    if not needs_reply:
        st.markdown(
            '<div class="section-card">'
            '<div class="section-head"><div class="section-title">📨 회신 필요</div></div>'
            '<div class="reply-text">회신할 메일이 없습니다 🎉</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        replies_sorted = sorted(
            needs_reply, key=lambda m: m["date"], reverse=True
        )[:5]
        rows_html = ""
        for m in replies_sorted:
            rows_html += _reply_row(
                name=m.get("from_name") or m["from"],
                dt=datetime.fromisoformat(m["date"]),
                body=m.get("summary") or "",
            )
        section_html = (
            '<div class="section-card">'
            '<div class="section-head">'
            '<div class="section-title">📨 회신 필요</div>'
            '<div class="filter-pills">'
            f'<span class="filter-pill active">전체 ({len(needs_reply)})</span>'
            '<span class="filter-pill">오늘</span>'
            '<span class="filter-pill">이번 주</span>'
            "</div>"
            "</div>"
            f"{rows_html}"
            "</div>"
        )
        st.markdown(section_html, unsafe_allow_html=True)

with c2:
    if not week_schedules:
        st.markdown(
            '<div class="section-card">'
            '<div class="section-head"><div class="section-title">📅 다가오는 일정</div></div>'
            '<div class="reply-text">이번 주 일정이 없습니다.</div>'
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        upcoming = sorted(week_schedules, key=lambda x: x[0])[:5]
        rows_html = ""
        # 마감 임박 기준: 지나지 않았고 내일 23:59 이전까지
        tomorrow_end = (now + timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        for parsed, sched, m in upcoming:
            urgent = now <= parsed <= tomorrow_end
            rows_html += _sched_row(
                parsed=parsed,
                sched_text=sched["text"],
                subject=m.get("subject") or "(제목 없음)",
                sender=m.get("from_name") or m["from"],
                urgent=urgent,
            )
        section_html = (
            '<div class="section-card">'
            '<div class="section-head">'
            '<div class="section-title">📅 다가오는 일정</div>'
            "</div>"
            f"{rows_html}"
            "</div>"
        )
        st.markdown(section_html, unsafe_allow_html=True)

st.divider()

# ─── 컨택트별 활동 + 상태 분포 ───────────────────────────────────────────
b1, b2 = st.columns(2)

# 컨택트별 활동 — 최근 7일 히트맵
with b1:
    top = sorted(senders, key=lambda s: s["message_count"], reverse=True)[:8]
    days_back = [(now - timedelta(days=i)).date() for i in range(6, -1, -1)]
    rows_html = ""
    for s in top:
        sender_msgs = [m for m in all_messages if m["sender_email"] == s["email"]]
        counts = [
            sum(1 for m in sender_msgs if _naive(m["date"]).date() == d)
            for d in days_back
        ]
        rows_html += _heatmap_row(
            name=s.get("name") or s["email"],
            counts=counts,
            total=s["message_count"],
        )

    section_html = (
        '<div class="section-card">'
        '<div class="section-head">'
        '<div class="section-title">👥 컨택트별 활동 (최근 7일)</div>'
        f'<div class="section-meta">상위 {len(top)}명</div>'
        "</div>"
        f"{rows_html}"
        "</div>"
    )
    st.markdown(section_html, unsafe_allow_html=True)

# 메일 상태 분포 — SVG 도넛 + 커스텀 범례 + 인사이트
with b2:
    counter = Counter(m.get("status") or "참고" for m in all_messages)
    total_msgs = sum(counter.values()) or 1
    # 정해진 순서로 슬라이스 구성
    ordered = [
        (lbl, counter.get(lbl, 0), _STATUS_COLORS[lbl])
        for lbl in ["회신 필요", "진행 중", "완료", "참고"]
    ]
    donut_html = _donut_svg(ordered, total_msgs)
    legend_html = "".join(
        _legend_row(lbl, color, count / total_msgs * 100)
        for lbl, count, color in ordered
    )

    # 인사이트 — 회신 필요 비율 20% 초과 시 추천 메시지
    insight_html = ""
    if all_messages and needs_reply:
        pct = len(needs_reply) / len(all_messages) * 100
        if pct > 20:
            top_emails = [
                e for e, _ in
                Counter(m["sender_email"] for m in needs_reply).most_common(2)
            ]
            names: list[str] = []
            seen: set[str] = set()
            for e in top_emails:
                n = next(
                    (s.get("name") or s["email"] for s in senders if s["email"] == e),
                    e,
                )
                if n not in seen:
                    names.append(n)
                    seen.add(n)
            insight_html = (
                f'<div class="insight-card">'
                f'<b>인사이트:</b> 이번 주 "회신 필요" 비율이 {pct:.0f}%로 평소보다 높아요. '
                f'{escape(", ".join(names))} 회신을 먼저 챙기는 걸 추천합니다.'
                f"</div>"
            )

    section_html = (
        '<div class="section-card">'
        '<div class="section-head">'
        '<div class="section-title">🍩 메일 상태 분포</div>'
        f'<div class="section-meta">전체 {total_msgs}건</div>'
        "</div>"
        '<div class="donut-wrap">'
        f'<div class="donut-svg">{donut_html}</div>'
        f'<div class="donut-legend">{legend_html}</div>'
        "</div>"
        f"{insight_html}"
        "</div>"
    )
    st.markdown(section_html, unsafe_allow_html=True)
