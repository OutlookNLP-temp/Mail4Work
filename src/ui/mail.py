import os
from datetime import datetime

import httpx
import streamlit as st

# 0. 설정 — API base URL은 환경변수로 오버라이드 가능
API_BASE = os.getenv("MAIL4WORK_API", "http://localhost:8000")

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="MailChat Log")

# 메신저 느낌 CSS
st.markdown(
    """
    <style>
    .chat-block {
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #e6e9ef;
    }
    .my-msg { background-color: #e3f2fd; }
    .other-msg { background-color: #f5f5f5; }
    </style>
    """,
    unsafe_allow_html=True,
)


# 2. API 호출 (캐시 — 60초 TTL, "동기화" 버튼으로 수동 무효화)
@st.cache_data(ttl=60)
def fetch_senders() -> list[dict]:
    # 컨택트 리스트 (자기 자신 제외)
    r = httpx.get(f"{API_BASE}/senders", timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=60)
def fetch_messages(sender_id: str) -> dict:
    # 컨택트와의 메시지 + 통계 — 첫 호출 시 KoBART 요약 lazy 트리거되므로 timeout 넉넉히
    r = httpx.get(
        f"{API_BASE}/senders/{sender_id}/messages", timeout=120
    )
    r.raise_for_status()
    return r.json()


def trigger_sync() -> dict:
    # 사용자 동기화 트리거
    r = httpx.post(f"{API_BASE}/sync", timeout=300)
    r.raise_for_status()
    return r.json()


# 3. 사이드바: 채팅방 목록
st.sidebar.title("💬 Mail Groups")

# 동기화 버튼
if st.sidebar.button("🔄 새 메일 동기화"):
    with st.spinner("IMAP 동기화 중..."):
        try:
            result = trigger_sync()
            st.cache_data.clear()
            st.sidebar.success(f"가져옴: {result['fetched']}건")
        except Exception as e:
            st.sidebar.error(f"동기화 실패: {e}")

# 컨택트 로드
try:
    senders = fetch_senders()
except Exception as e:
    st.sidebar.error(f"API 연결 실패: {e}")
    st.stop()

if not senders:
    st.sidebar.info("아직 메일이 없습니다. 동기화를 실행하세요.")
    st.stop()

# 드롭다운에 보일 라벨: "이름 <이메일>"
sender_options = {
    f"{s.get('name') or s['email']} <{s['email']}>": s for s in senders
}
selected_label = st.sidebar.selectbox(
    "메일 상대 선택", list(sender_options.keys())
)
selected_sender = sender_options[selected_label]

# 4. 메인 화면 구성
display_name = selected_sender.get("name") or selected_sender["email"]
st.title(f"✉️ {display_name}님과의 메일")
st.caption(selected_sender["email"])
st.divider()

# 5. 메시지 + 통계 로드
try:
    payload = fetch_messages(selected_sender["email"])
except Exception as e:
    st.error(f"메시지 로드 실패: {e}")
    st.stop()

messages = payload["messages"]
stats = payload["stats"]

# 6. 채팅 인터페이스 출력
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

                # 헤더
                sender_label = "나" if is_me else (
                    msg.get("from_name") or msg["from"]
                )
                st.markdown(f"**{sender_label}**")

                # 시각 (ISO 8601 → 보기 좋게)
                ts = datetime.fromisoformat(msg["date"])
                st.caption(f"🕒 {ts.strftime('%Y-%m-%d %H:%M')}")

                # 요약 (있으면)
                if msg.get("summary"):
                    st.info(msg["summary"])

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

# 7. 사이드바: 분석 정보
with st.sidebar:
    st.divider()
    st.subheader("📊 Room Insight")

    st.metric("총 메시지", stats["total"])
    c1, c2 = st.columns(2)
    c1.metric("보낸 메일", stats["sent"])
    c2.metric("받은 메일", stats["received"])
