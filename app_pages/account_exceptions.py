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
            "GL Account Number",
            "Ledger",
            "Functional Area",
            "Company Code",
            "Profit Center",
            "Cost Center",            
            "Enabled",
            "Changed By",
            "Changed On"
        FROM CONFIG.SILVER."Account_Exception_MasterData" WHERE "Enabled" = true 
        ORDER BY "GL Account Number"
    """).to_pandas()
    df["Enabled"] = df["Enabled"].astype(bool)
    return df

def write_events(events: list[dict]):
    if not events:
        return
    
    # SMS: In a container, setup, this gets the owner (svc. user) not the viewer
    # user = session.sql("SELECT CURRENT_USER()").collect()[0][0]
    
    # This will get the viewer's user identity
    user = st.user.user_name
    
    for evt in events:
        evt["Changed By"] = user
        payload = json.dumps(evt)
        session.sql(f"""
            INSERT INTO CONFIG.RAW.ACCOUNT_EXCEPTION_EVENT_DATA
                (SERIALIZED_SOURCE, EVENT_TIME)
            SELECT
                PARSE_JSON('{payload.replace("'", "''")}'),
                CURRENT_TIMESTAMP()
        """).collect()


master_df = load_master_data()

if st.button("🔄 Refresh Data", key="refresh"):
    st.cache_data.clear()
    st.rerun()
    
tab_edit, tab_add = st.tabs(["Edit Existing", "Add New"])

with tab_edit:
    st.caption("Edit rows below. Changes are saved as change events with full audit trail.")

    entity_filter = st.selectbox(
        "Filter by GL Account Number",
        options=["All"] + sorted(master_df["GL Account Number"].unique().tolist()),
        key="entity_filter",
    )

    if entity_filter == "All":
        filtered_df = master_df
    else:
        filtered_df = master_df[master_df["GL Account Number"] == entity_filter].reset_index(drop=True)

    display_df = filtered_df.copy()
    display_df.insert(0, "Delete", False)

    edited_df = st.data_editor(
        display_df,
        key=f"editor_{entity_filter}",
        disabled=["ID", "Changed By", "Changed On", "Enabled"],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "ID": None,
            "Enabled": None,
        },        
    )

    if st.button("Save Changes", key="save_edits", type="primary"):
        changes = []
        overlap_warnings = []
        deletes = []
        for idx in range(len(filtered_df)):
            orig = filtered_df.iloc[idx]
            curr = edited_df.iloc[idx]

            if curr["Delete"]:
                deletes.append(orig["ID"])
                changes.append({
                    "ID": orig["ID"],
                    "GL Account Number": orig["GL Account Number"],
                    "Ledger": orig["Ledger"],
                    "Functional Area": orig["Functional Area"],
                    "Company Code": orig["Company Code"],
                    "Profit Center": orig["Profit Center"],
                    "Cost Center": orig["Cost Center"],
                    "Enabled": False,
                })
                continue

            curr_comparable = curr.drop("Delete")
            if not orig.equals(curr_comparable):
                gl_changed = (
                    orig["GL Account Number"] != curr["GL Account Number"]
                    or orig["Ledger"] != curr["Ledger"]
                    or orig["Functional Area"] != curr["Functional Area"]
                    or orig["Company Code"] != curr["Company Code"]
                    or orig["Profit Center"] != curr["Profit Center"]
                    or orig["Cost Center"] != curr["Cost Center"]
                )

                changes.append({
                    "ID": orig["ID"],
                    "GL Account Number": orig["GL Account Number"],
                    "Ledger": orig["Ledger"],
                    "Functional Area": orig["Functional Area"],
                    "Company Code": orig["Company Code"],
                    "Profit Center": orig["Profit Center"],
                    "Cost Center": orig["Cost Center"],
                    "Enabled": bool(curr["Enabled"]),
                })

        if changes:
            if deletes:
                st.warning(f"Disabling {len(deletes)} rule(s).")
            write_events(changes)
            st.cache_data.clear()
            st.success(f"Saved {len(changes)} item(s). Refresh to see updates.")
        else:
            st.info("No changes detected.")
with tab_add:
    st.subheader("Add New Item")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        new_gl = st.text_input("GL Number")
    with col2:
        new_ledger = st.text_input("Ledger")
    with col3:
        new_fa = st.text_input("Functional Area")
    with col4:
        new_company = st.text_input("Company Code")
    with col5:
        new_pc = st.text_input("Proft Center")
    with col6:
        new_cc = st.text_input("Cost Center")
        

    if st.button("Add Mapping", type="primary"):
        if not all([new_entity, new_min, new_max]):
            st.error("All fields are required.")
        else:
            new_id = str(uuid.uuid4())
            evt = {
                "ID": new_id,
                "GL Account Number": new_gl,
                "Ledger": new_ledger,
                "Functional Area": new_fa,
                "Company Code": new_company,
                "Profit Center": new_pc,
                "Cost Center": new_cc,
                "Enabled": True,
            }
            write_events([evt])
            st.cache_data.clear()
            st.success(f"Added rule: {new_id}. Refresh to see updates.")
