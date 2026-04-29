import streamlit as st

# 페이지 메타 (최상위 진입점에서만 set)
st.set_page_config(layout="wide", page_title="Mail4Work")

# 멀티페이지 네비게이션
dashboard = st.Page(
    "_dashboard.py",
    title="Dashboard",
    icon=":material/dashboard:",
    default=True,
)
mail_groups = st.Page(
    "_mail_groups.py",
    title="Mail Groups",
    icon=":material/forum:",
)

pg = st.navigation([dashboard, mail_groups])
pg.run()
