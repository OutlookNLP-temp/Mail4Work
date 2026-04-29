import os

import httpx
import streamlit as st

API_BASE = os.getenv("MAIL4WORK_API", "http://localhost:8000")


@st.cache_data(ttl=60)
def fetch_senders() -> list[dict]:
    # 컨택트 리스트 (자기 자신 제외)
    r = httpx.get(f"{API_BASE}/senders", timeout=10)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=60)
def fetch_messages(sender_id: str) -> dict:
    # 컨택트와의 메시지 + 통계 (요약/상태/일정 lazy 트리거)
    r = httpx.get(f"{API_BASE}/senders/{sender_id}/messages", timeout=180)
    r.raise_for_status()
    return r.json()


@st.cache_data(ttl=30)
def fetch_sync_status() -> dict:
    r = httpx.get(f"{API_BASE}/sync/status", timeout=5)
    r.raise_for_status()
    return r.json()


def trigger_sync() -> dict:
    # 동기화 트리거 (긴 fetch 가능성 → 5분 타임아웃)
    r = httpx.post(f"{API_BASE}/sync", timeout=300)
    r.raise_for_status()
    return r.json()


def render_sync_button() -> None:
    # 사이드바 공통: 동기화 버튼
    if st.sidebar.button("🔄 새 메일 동기화"):
        with st.spinner("IMAP 동기화 중..."):
            try:
                result = trigger_sync()
                st.cache_data.clear()
                st.sidebar.success(f"가져옴: {result['fetched']}건")
            except Exception as e:
                st.sidebar.error(f"동기화 실패: {e}")
