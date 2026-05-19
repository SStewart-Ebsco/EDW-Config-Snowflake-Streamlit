import streamlit as st
import pandas as pd
import json
import uuid

session = st.session_state["conn"].session()

@st.cache_data(ttl=30)
def load_master_data():
    df = session.sql("""
        SELECT
            "(PK) ID"           AS "ID",
            "windows_user_nm",
            "domain",
            "sap_user_nm",
            "email_name",
            "domain2",
            "Enabled",
            "Changed By",
            "Changed On"
        FROM CONFIG.SILVER."SAP_User_Mapping_MasterData" WHERE "Enabled" = true
        ORDER BY "windows_user_nm"
    """).to_pandas()
    df["Enabled"] = df["Enabled"].astype(bool)
    return df

def write_events(events: list[dict]):
    if not events:
        return
    user = st.user.user_name
    for evt in events:
        evt["Changed By"] = user
        payload = json.dumps(evt)
        session.sql(f"""
            INSERT INTO CONFIG.RAW.SAP_USER_MAPPING_EVENT_DATA
                (SERIALIZED_SOURCE, EVENT_TIME)
            SELECT
                PARSE_JSON('{payload.replace("'", "''")}'),
                CURRENT_TIMESTAMP()
        """).collect()


master_df = load_master_data()

if st.button("\U0001f504 Refresh Data", key="sap_refresh"):
    st.cache_data.clear()
    st.rerun()

tab_edit, tab_add = st.tabs(["Edit Existing", "Add New"])

with tab_edit:
    st.caption("Edit rows below. Changes are saved as change events with full audit trail.")

    user_filter = st.selectbox(
        "Filter by Windows User",
        options=["All"] + sorted(master_df["windows_user_nm"].unique().tolist()),
        key="sap_user_filter",
    )

    if user_filter == "All":
        filtered_df = master_df
    else:
        filtered_df = master_df[master_df["windows_user_nm"] == user_filter].reset_index(drop=True)

    display_df = filtered_df.copy()
    display_df.insert(0, "Delete", False)

    edited_df = st.data_editor(
        display_df,
        key=f"sap_editor_{user_filter}",
        disabled=["ID", "Changed By", "Changed On", "Enabled"],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "ID": None,
            "Enabled": None,
        },
    )

    if st.button("Save Changes", key="sap_save_edits", type="primary"):
        changes = []
        deletes = []
        for idx in range(len(filtered_df)):
            orig = filtered_df.iloc[idx]
            curr = edited_df.iloc[idx]

            if curr["Delete"]:
                deletes.append(orig["ID"])
                changes.append({
                    "ID": orig["ID"],
                    "windows_user_nm": orig["windows_user_nm"],
                    "domain": orig["domain"],
                    "sap_user_nm": orig["sap_user_nm"],
                    "email_name": orig["email_name"],
                    "domain2": orig["domain2"],
                    "Enabled": False,
                })
                continue

            curr_comparable = curr.drop("Delete")
            if not orig.equals(curr_comparable):
                changes.append({
                    "ID": orig["ID"],
                    "windows_user_nm": curr["windows_user_nm"],
                    "domain": curr["domain"],
                    "sap_user_nm": curr["sap_user_nm"],
                    "email_name": curr["email_name"],
                    "domain2": curr["domain2"],
                    "Enabled": bool(curr["Enabled"]),
                })

        if changes:
            if deletes:
                st.warning(f"Disabling {len(deletes)} mapping(s).")
            write_events(changes)
            st.cache_data.clear()
            st.success(f"Saved {len(changes)} item(s). Refresh to see updates.")
        else:
            st.info("No changes detected.")

with tab_add:
    st.subheader("Add New Mapping")
    col1, col2, col3 = st.columns(3)
    with col1:
        new_windows_user = st.text_input("Windows User", key="sap_new_win_user")
    with col2:
        new_domain = st.text_input("Domain", key="sap_new_domain")
    with col3:
        new_sap_user = st.text_input("SAP User", key="sap_new_sap_user")
    col4, col5 = st.columns(2)
    with col4:
        new_email = st.text_input("Email Name", key="sap_new_email")
    with col5:
        new_domain2 = st.text_input("Domain2", key="sap_new_domain2")

    if st.button("Add Mapping", type="primary", key="sap_add"):
        if not all([new_windows_user, new_domain, new_sap_user]):
            st.error("Windows User, Domain, and SAP User are required.")
        else:
            new_id = str(uuid.uuid4())
            evt = {
                "ID": new_id,
                "windows_user_nm": new_windows_user,
                "domain": new_domain,
                "sap_user_nm": new_sap_user,
                "email_name": new_email,
                "domain2": new_domain2,
                "Enabled": True,
            }
            write_events([evt])
            st.cache_data.clear()
            st.success(f"Added mapping: {new_id}. Refresh to see updates.")
