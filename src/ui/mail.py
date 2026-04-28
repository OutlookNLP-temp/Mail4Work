import streamlit as st
import pandas as pd

# 0. 설정 상수 (필요에 따라 변경 가능)
MY_EMAIL = "me@service.com"

# 1. 페이지 설정
st.set_page_config(layout="wide", page_title="MailChat Log")

# 블록 디자인을 위한 CSS 스타일링
st.markdown(f"""
    <style>
    /* 메신저 느낌을 위한 카드 스타일 */
    .chat-block {{
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border: 1px solid #e6e9ef;
    }}
    /* 내 메시지 배경색 (우측) */
    .my-msg {{ background-color: #e3f2fd; }}
    /* 상대방 메시지 배경색 (좌측) */
    .other-msg {{ background-color: #f5f5f5; }}
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 로드
@st.cache_data
def load_data():
    # 데이터 경로를 실제 파일명으로 확인해주세요
    df = pd.read_excel("mail_chat_service_dataset.xlsx", sheet_name="MailData")
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    return df

df = load_data()

# 3. 사이드바: 채팅방 목록
st.sidebar.title("💬 Mail Groups")
# MY_EMAIL 상수를 제외한 나머지 연락처 추출
other_parties = df[df['Sender'] != MY_EMAIL]['Sender'].unique()
selected_party = st.sidebar.selectbox("메일 상대 선택", other_parties)

# 4. 메인 화면 구성
st.title(f"✉️ {selected_party}님과의 메일")
st.divider()

# 필터링: (상대방 -> 나) 또는 (나 -> 상대방)
chat_logs = df[
    (df['Sender'] == selected_party) | 
    ((df['Sender'] == MY_EMAIL) & (df['Receiver'] == selected_party))
].sort_values('Timestamp')

# 5. 채팅 인터페이스 출력
if chat_logs.empty:
    st.info("대화 내역이 없습니다.")
else:
    for _, row in chat_logs.iterrows():
        is_me = row['Sender'] == MY_EMAIL
        
        # 2개의 컬럼을 만들어 위치 결정 (비율 1:4:1 등으로 조절 가능)
        # 내가 보낸 것이면 오른쪽 컬럼을 비우고 왼쪽 컬럼을 활용하거나 그 반대
        col_left, col_mid, col_right = st.columns([1, 8, 1])
        
        # 실제 메시지가 들어갈 타겟 컬럼 선정
        target_col = col_right if is_me else col_left
        avatar = "user" if is_me else "assistant"
        
        # 정렬을 위해 전체 폭을 조정하는 로직
        # Streamlit chat_message는 기본적으로 왼쪽 정렬이므로, 
        # '나'일 경우 빈 컬럼을 왼쪽에 배치하여 오른쪽으로 밀어냅니다.
        display_cols = st.columns([4, 4]) if not is_me else st.columns([4, 4])
        
        with (display_cols[0] if not is_me else display_cols[1]):
            with st.chat_message(avatar):
                # 블록 컨테이너 시작
                bg_style = "my-msg" if is_me else "other-msg"
                st.markdown(f'<div class="chat-block {bg_style}">', unsafe_allow_html=True)
                
                # 헤더
                st.markdown(f"**{'나' if is_me else row['Sender']}**")
                st.caption(f"🕒 {row['Timestamp'].strftime('%Y-%m-%d %H:%M')}")
                
                # 요약 내용
                st.info(row['AI_Summary_Draft'])
                
                # 상세 보기
                with st.expander("전문 보기"):
                    st.text(row['Raw_Text'])
                
                # 첨부파일
                if row.get('Has_Attachment') == "YES":
                    st.button(f"📎 File: {row['Message-ID'][:6]}", key=row['Message-ID'])
                
                st.markdown('</div>', unsafe_allow_html=True)

# 6. 오른쪽 사이드바: 분석 정보
with st.sidebar:
    st.divider()
    st.subheader("📊 Room Insight")
    
    total_msgs = len(chat_logs)
    sent_by_me = len(chat_logs[chat_logs['Sender'] == MY_EMAIL])
    received_by_me = total_msgs - sent_by_me
    
    st.metric("총 메시지", total_msgs)
    c1, c2 = st.columns(2)
    c1.metric("보낸 메일", sent_by_me)
    c2.metric("받은 메일", received_by_me)