import os
import streamlit as st

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
st.session_state["conn"] = conn

page = st.navigation([
    st.Page("app_pages/balance_sheet_mapping.py", title="Balance Sheet Mapping", icon=":material/map:"),
    st.Page("app_pages/balance_sheet_rules.py", title="Balance Sheet Rules", icon=":material/rule:"),
    st.Page("app_pages/investment_mapping.py", title="Investment Mapping", icon=":material/attach_money:"),
    st.Page("app_pages/account_exceptions.py", title="Account Exceptions", icon=":material/warning:"),
    st.Page("app_pages/gl_groupings.py", title="GL Groupings", icon=":material/category:"),
])

st.title(f"{page.title} Admin")

page.run()
