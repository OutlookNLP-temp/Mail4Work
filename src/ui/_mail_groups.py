from datetime import datetime

import streamlit as st

from _api import fetch_messages, fetch_senders, render_sync_button

# 상태 분류 라벨에 시각적 마커 부여
_STATUS_BADGE = {
    "회신 필요": "📨 회신 필요",
    "진행 중": "🚧 진행 중",
    "완료": "🔑 완료",
    "참고": "💡 참고",
}

# 메신저 느낌 CSS
st.markdown(
    """
    <style>
    .chat-block {
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border: 2px solid #e6e9ef;
    }
    .my-msg { background-color: #e3f2fd; }
    .other-msg { background-color: #f5f5f5; }
    </style>
    """,
    unsafe_allow_html=True,
)

# 사이드바: 동기화 + 채팅방 목록
st.sidebar.title("💬 Mail Groups")
render_sync_button()

try:
    senders = fetch_senders()
except Exception as e:
    st.sidebar.error(f"API 연결 실패: {e}")
    st.stop()

if not senders:
    st.sidebar.info("아직 메일이 없습니다. 동기화를 실행하세요.")
    st.stop()

sender_options = {
    f"{s.get('name') or s['email']} <{s['email']}>": s for s in senders
}
selected_label = st.sidebar.selectbox(
    "메일 상대 선택", list(sender_options.keys())
)
selected_sender = sender_options[selected_label]

# 메인 화면 — 컨택트 헤더
display_name = selected_sender.get("name") or selected_sender["email"]
st.title(f"✉️ {display_name}님과의 메일")
st.caption(selected_sender["email"])
st.divider()

# 메시지 + 통계 로드
try:
    payload = fetch_messages(selected_sender["email"])
except Exception as e:
    st.error(f"메시지 로드 실패: {e}")
    st.stop()

messages = payload["messages"]
stats = payload["stats"]

# 채팅 인터페이스 출력
if not messages:
    st.info("대화 내역이 없습니다.")
else:
    for msg in messages:
        is_me = msg["direction"] == "sent"

        # 좌/우 정렬: 받은 메일은 왼쪽, 보낸 메일은 오른쪽
        display_cols = st.columns([1, 1])
        target_col = display_cols[1] if is_me else display_cols[0]
        avatar = "user" if is_me else "assistant"

        with target_col:
            with st.chat_message(avatar):
                bg_style = "my-msg" if is_me else "other-msg"
                st.markdown(
                    f'<div class="chat-block {bg_style}">',
                    unsafe_allow_html=True,
                )

                # 헤더 — 발신자 + 상태 뱃지
                sender_label = "나" if is_me else (
                    msg.get("from_name") or msg["from"]
                )
                status = msg.get("status")
                badge = _STATUS_BADGE.get(status, "") if status else ""
                if badge:
                    st.markdown(f"**{sender_label}** &nbsp;&nbsp; {badge}")
                else:
                    st.markdown(f"**{sender_label}**")

                # 시각 (ISO 8601 → 보기 좋게)
                ts = datetime.fromisoformat(msg["date"])
                st.caption(f"🕒 {ts.strftime('%Y-%m-%d %H:%M')}")

                # 요약 (있으면)
                if msg.get("summary"):
                    st.info(msg["summary"])

                # 추출된 일정 (있으면)
                schedules = msg.get("schedules") or []
                if schedules:
                    lines = ["**📅 일정**"]
                    for s in schedules:
                        parsed = datetime.fromisoformat(s["parsed"])
                        lines.append(
                            f"- {parsed.strftime('%Y-%m-%d %H:%M')} — _{s['text']}_"
                        )
                    st.markdown("\n".join(lines))

                # 전문 보기
                if msg.get("body"):
                    with st.expander("전문 보기"):
                        st.text(msg["body"])

                # 첨부파일 (현재 backend에서 빈 배열 — 추후 구현)
                for att in msg.get("attachments", []):
                    st.button(
                        f"📎 {att['filename']}",
                        key=f"{msg['message_id']}-{att['idx']}",
                    )

                st.markdown("</div>", unsafe_allow_html=True)

# 사이드바 분석 정보
with st.sidebar:
    st.divider()
    st.subheader("📊 Room Insight")
    st.metric("총 메시지", stats["total"])
    c1, c2 = st.columns(2)
    c1.metric("보낸 메일", stats["sent"])
    c2.metric("받은 메일", stats["received"])
