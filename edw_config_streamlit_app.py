import os
import streamlit as st

st.set_page_config(page_title="EDW Config", layout="wide")

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
st.session_state["conn"] = conn

page = st.navigation([
    st.Page("app_pages/account_exceptions.py", title="Account Exceptions", icon=":material/account_balance:"),
    st.Page("app_pages/balance_sheet_rules.py", title="Balance Sheet Entites", icon=":material/category:"),
    st.Page("app_pages/balance_sheet_mapping.py", title="Balance Sheet Mapping", icon=":material/account_tree:"),
    st.Page("app_pages/business_unit_sort_order.py", title="Business Unit Sort Order", icon=":material/arrow_shape_up_stack:"),
    # st.Page("app_pages/cost_center_department.py", title="Cost Center Department", icon=":material/family_group:"),
    st.Page("app_pages/dso_analysis.py", title="DSO Analysis", icon=":material/money_bag:"),
    st.Page("app_pages/investment_mapping.py", title="Investment Mapping", icon=":material/attach_money:"),
    st.Page("app_pages/sap_user_mapping.py", title="SAP User Mapping", icon=":material/frame_person:"),
])

st.title(f"{page.title}")

page.run()
