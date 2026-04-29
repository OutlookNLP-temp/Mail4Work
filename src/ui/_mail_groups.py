import re
from datetime import datetime, timedelta
from html import escape

import streamlit as st

from _api import fetch_messages, fetch_senders, render_sync_button

# 상태 뱃지 — (아이콘, 배경색, 글자색)
_STATUS_BADGE = {
    "회신 필요": ("⚡", "#fff3e0", "#e07b1d"),
    "진행 중":   ("📌", "#e3f2fd", "#1976d2"),
    "완료":      ("✓",  "#e8f5e9", "#388e3c"),
    "참고":      ("💡", "#f3f4f6", "#6b7280"),
}

# 컨택트 아바타 색 팔레트 (이름 해시로 결정)
_AVATAR_PALETTE = [
    ("#fff1e0", "#e07b1d"),  # 오렌지
    ("#ede7f6", "#7e57c2"),  # 퍼플
    ("#e3f2fd", "#1976d2"),  # 블루
    ("#e8f5e9", "#43a047"),  # 그린
    ("#fce4ec", "#d81b60"),  # 핑크
    ("#fff8e1", "#f9a825"),  # 옐로우
    ("#e0f7fa", "#00838f"),  # 시안
]


def _avatar_palette(seed: str) -> tuple[str, str]:
    if not seed:
        return _AVATAR_PALETTE[0]
    return _AVATAR_PALETTE[sum(ord(c) for c in seed) % len(_AVATAR_PALETTE)]


def _avatar_char(name: str) -> str:
    name = (name or "?").strip() or "?"
    c = name[:1]
    return c.upper() if c.isascii() else c


def _avatar_html(seed: str, label: str | None = None, size: int = 40) -> str:
    bg, fg = _avatar_palette(seed)
    char = escape(_avatar_char(label if label is not None else seed))
    font_size = int(size * 0.42)
    return (
        f'<div class="avatar" style="width:{size}px;height:{size}px;'
        f'background:{bg};color:{fg};font-size:{font_size}px;">{char}</div>'
    )


def _naive(dt_str: str) -> datetime:
    dt = datetime.fromisoformat(dt_str)
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _relative_time(dt: datetime, now: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    if dt >= today:
        return dt.strftime("%H:%M")
    if dt >= yesterday:
        return "어제"
    days = (today.date() - dt.date()).days
    if days < 7:
        return f"{days}일 전"
    return f"{days // 7}주 전"


def _date_divider_label(d) -> str:
    today = datetime.now().date()
    if d == today:
        return "오늘"
    if d == today - timedelta(days=1):
        return "어제"
    return f"{d.year}년 {d.month}월 {d.day}일"


def _format_full_when(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    h = dt.hour
    ampm = "오전" if h < 12 else "오후"
    h12 = h % 12 or 12
    return f"{dt.year}년 {dt.month}월 {dt.day}일 {ampm} {h12}:{dt.minute:02d}"


def _badge_html(status: str | None) -> str:
    if not status or status not in _STATUS_BADGE:
        return ""
    icon, bg, fg = _STATUS_BADGE[status]
    return (
        f'<span class="status-badge" style="background:{bg};color:{fg};">'
        f"{icon} {escape(status)}</span>"
    )


def _schedule_html(parsed: datetime, text: str) -> str:
    if parsed.tzinfo is not None:
        parsed = parsed.replace(tzinfo=None)
    return (
        '<div class="sched-card">'
        f'<div class="sched-date-box">{parsed.month}/{parsed.day}</div>'
        '<div class="sched-info">'
        f'<div class="sched-when">{escape(_format_full_when(parsed))}</div>'
        f'<div class="sched-quote">"{escape(text)}"</div>'
        "</div>"
        "</div>"
    )


def _summary_html(text: str) -> str:
    return (
        '<div class="ai-summary">'
        '<div class="ai-summary-head">✨ AI 요약</div>'
        f'<div class="ai-summary-body">{escape(text)}</div>'
        "</div>"
    )


def _clean_full_body(body: str) -> str:
    # 전문 보기에서도 HTML 메일이면 태그 정리해서 보여줌
    body = (body or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    if "<html" in body.lower() or "<!doctype" in body.lower() or "<body" in body.lower():
        body = _TAG_RE.sub(" ", body)
        body = _ENTITY_RE.sub(" ", body)
        # 다중 공백·빈 줄 정리
        body = re.sub(r"[ \t]+", " ", body)
        body = re.sub(r"\n\s*\n\s*\n+", "\n\n", body).strip()
    return body


def _full_body_html(body: str, preview: str) -> str:
    # 미리보기보다 본문이 더 길 때만 details 토글로 노출
    cleaned = _clean_full_body(body)
    if not cleaned or len(cleaned) <= len(preview):
        return ""
    return (
        '<details class="full-body-toggle">'
        '<summary>전문 보기</summary>'
        f'<div class="full-body">{escape(cleaned)}</div>'
        "</details>"
    )


# 미리보기에서 HTML 태그/엔티티/멀티 공백 정리
_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_RE = re.compile(r"&[a-zA-Z#0-9]+;")
_WS_RE = re.compile(r"\s+")


def _body_preview(body: str, limit: int = 240) -> str:
    # 본문 미리보기 — HTML 메일이 섞여 있어도 깔끔하게 보이도록 태그 제거
    body = (body or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    if not body:
        return "(본문 없음)"
    # HTML 본문이면 태그 떼어내기
    if "<html" in body.lower() or "<!doctype" in body.lower() or "<body" in body.lower():
        body = _TAG_RE.sub(" ", body)
        body = _ENTITY_RE.sub(" ", body)
        body = _WS_RE.sub(" ", body).strip()
    first = body.split("\n\n", 1)[0]
    if len(first) > limit:
        first = first[:limit].rstrip() + "..."
    return first


_CSS = """
<style>
.block-container { padding-top: 3.5rem; padding-bottom: 1.5rem; max-width: 1180px; }

/* 사이드바 배경 톤 */
section[data-testid="stSidebar"] { background: #fafbfc; }

/* 공용 아바타 */
.avatar {
    border-radius: 50%;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    flex-shrink: 0;
}

/* ──────── 헤더 ──────── */
.mail-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 24px;
    padding: 4px 0 20px 0;
    border-bottom: 1px solid #eef0f3;
    margin-bottom: 16px;
}
.mail-header-left { display: flex; gap: 14px; align-items: center; }
.mail-header-info { display: flex; flex-direction: column; gap: 4px; }
.mh-name { font-size: 22px; font-weight: 700; color: #1a1a1a; line-height: 1.2; }
.mh-sub  { font-size: 13px; color: #6b7280; }
.mail-stats { display: flex; gap: 28px; padding-top: 4px; }
.mail-stat { text-align: center; min-width: 44px; }
.mail-stat-num   { font-size: 22px; font-weight: 700; color: #1a1a1a; line-height: 1; }
.mail-stat-label { font-size: 11px; color: #9ba3b3; margin-top: 6px; }

/* ──────── 날짜 구분선 ──────── */
.date-divider {
    text-align: center;
    margin: 22px 0 12px 0;
    color: #9ba3b3;
    font-size: 12px;
}

/* ──────── 메시지 행 ──────── */
.msg-row {
    display: flex;
    gap: 12px;
    margin: 14px 0;
    align-items: flex-start;
}
.msg-row.sent { flex-direction: row-reverse; }
.msg-content {
    display: flex;
    flex-direction: column;
    gap: 4px;
    max-width: 82%;
    flex: 1 1 auto;
    min-width: 0;
}
.msg-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 2px;
}
.msg-row.sent .msg-meta { justify-content: flex-end; }
.msg-name { font-weight: 700; color: #1a1a1a; font-size: 13px; }
.msg-time { font-size: 12px; color: #9ba3b3; }

.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 500;
    line-height: 1.4;
}

.msg-bubble {
    background: #ffffff;
    border: 1.5px solid #e9ecf0;
    border-radius: 14px;
    padding: 14px 18px;
    font-size: 14px;
    color: #1a1a1a;
    line-height: 1.7;
    text-align: left;
    overflow-wrap: anywhere;
    word-break: break-word;
    white-space: pre-wrap;
    align-self: stretch;
}
.msg-row.sent .msg-bubble {
    background: #f7fafd;
    border-color: #ecf2f8;
}

/* 인라인 일정 카드 */
.sched-card {
    display: flex;
    gap: 12px;
    align-items: center;
    background: #f7faff;
    border: 1px solid #e3eefc;
    border-radius: 10px;
    padding: 10px 12px;
    margin-top: 10px;
}
.sched-date-box {
    background: #e3f0fc;
    color: #1976d2;
    border-radius: 8px;
    padding: 6px 12px;
    font-weight: 700;
    font-size: 14px;
    min-width: 48px;
    text-align: center;
}
.sched-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.sched-when  { font-size: 13px; font-weight: 600; color: #1a1a1a; }
.sched-quote { font-size: 12px; color: #6b7280; font-style: italic; }

/* AI 요약 */
.ai-summary {
    margin-top: 10px;
    background: #f3f7ff;
    border-left: 3px solid #4a8df0;
    border-radius: 0 8px 8px 0;
    padding: 10px 14px;
}
.ai-summary-head { font-size: 12px; font-weight: 700; color: #2c3e64; margin-bottom: 4px; }
.ai-summary-body { font-size: 13px; color: #2c3e64; line-height: 1.55; }

/* 빈 상태 */
.empty-room {
    text-align: center;
    color: #9ba3b3;
    padding: 60px 0;
    font-size: 14px;
}

/* ──────── 사이드바 ──────── */
.sb-section-label {
    font-size: 12px;
    color: #6b7280;
    font-weight: 600;
    margin: 14px 4px 6px 4px;
}

/* 컨택트 카드 — 순수 HTML 시각, 버튼은 absolute 오버레이 */
.contact-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: 12px;
    background: transparent;
    transition: background 0.12s, box-shadow 0.12s;
}
.contact-card.active {
    background: #ffffff;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
}
.cc-avatar { flex-shrink: 0; }
.cc-text { flex: 1; min-width: 0; overflow: hidden; }
.cc-name {
    font-size: 13px;
    font-weight: 700;
    color: #1a1a1a;
    line-height: 1.3;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.cc-preview {
    font-size: 12px;
    color: #6b7280;
    line-height: 1.3;
    margin-top: 3px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.cc-right {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
    flex-shrink: 0;
}
.cc-time {
    font-size: 11px;
    color: #9ba3b3;
    white-space: nowrap;
    line-height: 1;
}
.unread-badge {
    background: #e69c4d;
    color: #ffffff;
    font-weight: 700;
    font-size: 12px;
    min-width: 22px;
    height: 22px;
    padding: 0 7px;
    border-radius: 999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 2px rgba(230, 156, 77, 0.25);
}

/* 동기화 버튼 — 검색창과 동일한 가로 폭 + 더 큰 세로 사이즈 */
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-of-type .stButton > button {
    background: #ffffff !important;
    border: 1px solid #e6e9ef !important;
    border-radius: 10px !important;
    padding: 14px 16px !important;
    min-height: 48px !important;
    height: 48px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    color: #1a1a1a !important;
    text-align: center !important;
    box-shadow: none !important;
    line-height: 1 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:first-of-type .stButton > button:hover {
    background: #f5f7fa !important;
    border-color: #c5dafd !important;
}

/* ── 컨택트 행 (stLayoutWrapper) — 카드 + absolute 오버레이 버튼 ── */
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] {
    position: relative;
    margin-bottom: 2px !important;
}

/* 호버 — 비활성 카드만 라벤더 톤 */
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"]:hover .contact-card:not(.active) {
    background: #ecf0f7;
}

/* 안쪽 stVerticalBlock 간격 제거 (카드와 버튼 겹침 보장) */
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] [data-testid="stVerticalBlock"] {
    gap: 0 !important;
}

/* 버튼이 들어있는 element-container를 카드 위에 absolute로 오버레이 */
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] [data-testid="stElementContainer"]:has(.stButton) {
    position: absolute;
    inset: 0;
    z-index: 2;
    margin: 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton {
    width: 100%;
    height: 100%;
}
/* 버튼 자체는 모든 상태에서 완전 투명 — 클릭만 잡음 */
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button,
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button:hover,
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button:focus,
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button:active,
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button:focus-visible,
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button[kind="primary"],
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button[kind="primary"]:hover,
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button[kind="primary"]:focus,
section[data-testid="stSidebar"] [data-testid="stLayoutWrapper"] .stButton > button[kind="primary"]:active {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-color: transparent !important;
    box-shadow: none !important;
    outline: none !important;
    color: transparent !important;
    width: 100%;
    height: 100%;
    min-height: 0 !important;
    padding: 0 !important;
    border-radius: 12px;
    cursor: pointer;
}

/* 전문 보기 토글 (네이티브 details 사용) */
.full-body-toggle {
    margin-top: 12px;
}
.full-body-toggle > summary {
    cursor: pointer;
    list-style: none;
    color: #6b7280;
    font-size: 12px;
    font-weight: 500;
    padding: 4px 0;
    user-select: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
}
.full-body-toggle > summary::-webkit-details-marker { display: none; }
.full-body-toggle > summary::marker { content: ""; }
.full-body-toggle > summary::before {
    content: "›";
    display: inline-block;
    transition: transform 0.15s;
    font-size: 14px;
    color: #9ba3b3;
}
.full-body-toggle[open] > summary::before { transform: rotate(90deg); }
.full-body {
    background: #f5f5f5;
    border-radius: 10px;
    padding: 14px 16px;
    margin-top: 8px;
    font-size: 13px;
    color: #444;
    line-height: 1.7;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
}
.msg-row.sent .full-body { background: #eef3f9; color: #333; }
</style>
"""


# ─── 페이지 시작 ──────────────────────────────────────────────────────────
st.markdown(_CSS, unsafe_allow_html=True)

render_sync_button()

# 컨택트 데이터 로드
try:
    senders = fetch_senders()
except Exception as e:
    st.sidebar.error(f"API 연결 실패: {e}")
    st.stop()

if not senders:
    st.sidebar.info("아직 메일이 없습니다. 동기화를 실행하세요.")
    st.stop()


def _contact_meta(email: str) -> dict:
    # 컨택트 카드용 메타: 최신 메시지 제목 + 회신 필요 카운트
    # fetch_messages가 자체 캐시되므로 재호출 비용 낮음
    try:
        payload = fetch_messages(email)
    except Exception:
        return {"preview": "", "unread": 0, "latest": None}
    msgs = payload["messages"]
    if not msgs:
        return {"preview": "(메시지 없음)", "unread": 0, "latest": None}
    latest = max(msgs, key=lambda m: m["date"])
    subject = (latest.get("subject") or "(제목 없음)").strip()
    if len(subject) > 28:
        subject = subject[:28] + "…"
    return {
        "preview": subject,
        "unread": sum(1 for m in msgs if m.get("status") == "회신 필요"),
        "latest": latest["date"],
    }


# 사이드바 — 검색 + 컨택트 리스트
st.sidebar.markdown(
    f'<div class="sb-section-label">컨택트 ({len(senders)})</div>',
    unsafe_allow_html=True,
)
search_q = st.sidebar.text_input(
    "search",
    placeholder="🔍 이름 또는 이메일 검색",
    label_visibility="collapsed",
)


def _matches(s: dict, q: str) -> bool:
    if not q:
        return True
    q = q.lower()
    return q in (s.get("name") or "").lower() or q in s["email"].lower()


filtered = [s for s in senders if _matches(s, search_q)]

# 선택 컨택트 상태 — 검색 변경/초기 진입 시 보정
emails_in_view = {s["email"] for s in filtered or senders}
if (
    "selected_email" not in st.session_state
    or st.session_state.selected_email not in {s["email"] for s in senders}
):
    st.session_state.selected_email = (filtered or senders)[0]["email"]
elif st.session_state.selected_email not in emails_in_view and filtered:
    st.session_state.selected_email = filtered[0]["email"]

now = datetime.now()

# 메타 집계 (최신순 정렬에도 사용)
meta_by_email: dict[str, dict] = {}
with st.spinner("컨택트 정보 동기화..."):
    for s in senders:
        meta_by_email[s["email"]] = _contact_meta(s["email"])

# 가장 최근 메시지 시각 기준 정렬
def _sort_key(s: dict) -> str:
    m = meta_by_email.get(s["email"], {})
    return m.get("latest") or s["latest_at"]


sorted_contacts = sorted(filtered, key=_sort_key, reverse=True)

for s in sorted_contacts:
    name = s.get("name") or s["email"]
    meta = meta_by_email.get(s["email"], {})
    latest_iso = meta.get("latest") or s["latest_at"]
    latest_dt = datetime.fromisoformat(latest_iso)
    rel = _relative_time(latest_dt, now)
    is_active = s["email"] == st.session_state.selected_email
    preview = meta.get("preview") or s["email"]
    unread = meta.get("unread") or 0

    badge_html = (
        f'<span class="unread-badge">{unread}</span>' if unread else ""
    )
    card_html = (
        f'<div class="contact-card{" active" if is_active else ""}">'
        f'<div class="cc-avatar">{_avatar_html(name, size=38)}</div>'
        '<div class="cc-text">'
        f'<div class="cc-name">{escape(name)}</div>'
        f'<div class="cc-preview">{escape(preview)}</div>'
        '</div>'
        '<div class="cc-right">'
        f'<div class="cc-time">{escape(rel)}</div>'
        f'{badge_html}'
        '</div>'
        '</div>'
    )
    row = st.sidebar.container()
    with row:
        st.markdown(card_html, unsafe_allow_html=True)
        if st.button(
            " ",
            key=f"contact-{s['sender_id']}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.selected_email = s["email"]
            st.rerun()

selected_sender = next(
    (s for s in senders if s["email"] == st.session_state.selected_email),
    senders[0],
)

# ─── 메시지 로드 ──────────────────────────────────────────────────────────
try:
    payload = fetch_messages(selected_sender["email"])
except Exception as e:
    st.error(f"메시지 로드 실패: {e}")
    st.stop()

messages = payload["messages"]
stats = payload["stats"]

# ─── 헤더 ────────────────────────────────────────────────────────────────
display_name = selected_sender.get("name") or selected_sender["email"]

# 활동 시작 = 가장 오래된 메시지의 연/월
oldest = min((_naive(m["date"]) for m in messages), default=None)
start_str = (
    f"활동 시작 {oldest.year}년 {oldest.month}월" if oldest else "—"
)

need_reply_cnt = sum(1 for m in messages if m.get("status") == "회신 필요")

avatar_html = _avatar_html(display_name, size=48)

st.markdown(
    f'<div class="mail-header">'
    f'<div class="mail-header-left">{avatar_html}'
    '<div class="mail-header-info">'
    f'<div class="mh-name">{escape(display_name)}님과의 메일</div>'
    f'<div class="mh-sub">{escape(selected_sender["email"])} · {escape(start_str)}</div>'
    "</div></div>"
    '<div class="mail-stats">'
    f'<div class="mail-stat"><div class="mail-stat-num">{need_reply_cnt}</div>'
    '<div class="mail-stat-label">회신 필요</div></div>'
    f'<div class="mail-stat"><div class="mail-stat-num">{stats["sent"]}</div>'
    '<div class="mail-stat-label">보낸 메일</div></div>'
    f'<div class="mail-stat"><div class="mail-stat-num">{stats["received"]}</div>'
    '<div class="mail-stat-label">받은 메일</div></div>'
    f'<div class="mail-stat"><div class="mail-stat-num">{stats["total"]}</div>'
    '<div class="mail-stat-label">총 메시지</div></div>'
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)

# ─── 채팅 영역 ────────────────────────────────────────────────────────────
if not messages:
    st.markdown(
        '<div class="empty-room">대화 내역이 없습니다.</div>',
        unsafe_allow_html=True,
    )
else:
    sorted_msgs = sorted(messages, key=lambda m: _naive(m["date"]))

    last_date = None
    for m in sorted_msgs:
        ts = _naive(m["date"])
        if last_date != ts.date():
            st.markdown(
                f'<div class="date-divider">{escape(_date_divider_label(ts.date()))}</div>',
                unsafe_allow_html=True,
            )
            last_date = ts.date()

        is_me = m["direction"] == "sent"
        sender_label = "나" if is_me else (m.get("from_name") or m["from"])
        # 보낸 메일 아바타는 일관되게 "나" 시드, 받은 메일은 컨택트 이름 시드
        avatar = _avatar_html(
            seed="나-self" if is_me else display_name,
            label=sender_label,
            size=40,
        )

        body = m.get("body") or ""
        main_text = _body_preview(body, 240)
        sched_html = "".join(
            _schedule_html(datetime.fromisoformat(s["parsed"]), s["text"])
            for s in (m.get("schedules") or [])
        )
        summary_block = _summary_html(m["summary"]) if m.get("summary") else ""

        meta_html = (
            '<div class="msg-meta">'
            f'<span class="msg-name">{escape(sender_label)}</span>'
            f'{_badge_html(m.get("status"))}'
            f'<span class="msg-time">{ts.strftime("%H:%M")}</span>'
            "</div>"
        )

        full_body_block = _full_body_html(body, main_text)

        bubble_html = (
            f'<div class="msg-bubble">{escape(main_text)}'
            f"{sched_html}{summary_block}{full_body_block}"
            "</div>"
        )

        row_class = "msg-row sent" if is_me else "msg-row"
        st.markdown(
            f'<div class="{row_class}">{avatar}'
            f'<div class="msg-content">{meta_html}{bubble_html}</div>'
            "</div>",
            unsafe_allow_html=True,
        )

        # 첨부파일
        for att in m.get("attachments", []):
            st.button(
                f"📎 {att['filename']}",
                key=f"att-{m['message_id']}-{att['idx']}",
            )
