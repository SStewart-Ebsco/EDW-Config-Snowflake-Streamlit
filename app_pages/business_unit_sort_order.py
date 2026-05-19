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
            "Business Unit",
            "Short Name",
            "Group",
            "Sort Order",
            "Enabled",
            "Changed By",
            "Changed On"
        FROM CONFIG.SILVER."Business_Unit_Sort_Order_MasterData" WHERE "Enabled" = true
        ORDER BY "Sort Order"
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
            INSERT INTO CONFIG.RAW.BUSINESS_UNIT_SORT_ORDER_EVENT_DATA
                (SERIALIZED_SOURCE, EVENT_TIME)
            SELECT
                PARSE_JSON('{payload.replace("'", "''")}'),
                CURRENT_TIMESTAMP()
        """).collect()


master_df = load_master_data()

if st.button("\U0001f504 Refresh Data", key="buso_refresh"):
    st.cache_data.clear()
    st.rerun()

tab_edit, tab_add = st.tabs(["Edit Existing", "Add New"])

with tab_edit:
    st.caption("Edit rows below. Changes are saved as change events with full audit trail.")

    group_filter = st.selectbox(
        "Filter by Group",
        options=["All"] + sorted(master_df["Group"].unique().tolist()),
        key="buso_group_filter",
    )

    if group_filter == "All":
        filtered_df = master_df
    else:
        filtered_df = master_df[master_df["Group"] == group_filter].reset_index(drop=True)

    display_df = filtered_df.copy()
    display_df.insert(0, "Delete", False)

    edited_df = st.data_editor(
        display_df,
        key=f"buso_editor_{group_filter}",
        disabled=["ID", "Changed By", "Changed On", "Enabled"],
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "ID": None,
            "Enabled": None,
        },
    )

    if st.button("Save Changes", key="buso_save_edits", type="primary"):
        changes = []
        deletes = []
        for idx in range(len(filtered_df)):
            orig = filtered_df.iloc[idx]
            curr = edited_df.iloc[idx]

            if curr["Delete"]:
                deletes.append(orig["ID"])
                changes.append({
                    "ID": orig["ID"],
                    "Business Unit": orig["Business Unit"],
                    "Short Name": orig["Short Name"],
                    "Group": orig["Group"],
                    "Sort Order": int(orig["Sort Order"]),
                    "Enabled": False,
                })
                continue

            curr_comparable = curr.drop("Delete")
            if not orig.equals(curr_comparable):
                changes.append({
                    "ID": orig["ID"],
                    "Business Unit": curr["Business Unit"],
                    "Short Name": curr["Short Name"],
                    "Group": curr["Group"],
                    "Sort Order": int(curr["Sort Order"]),
                    "Enabled": bool(curr["Enabled"]),
                })

        if changes:
            if deletes:
                st.warning(f"Disabling {len(deletes)} record(s).")
            write_events(changes)
            st.cache_data.clear()
            st.success(f"Saved {len(changes)} item(s). Refresh to see updates.")
        else:
            st.info("No changes detected.")

with tab_add:
    st.subheader("Add New Record")
    col1, col2 = st.columns(2)
    with col1:
        new_bu = st.text_input("Business Unit", key="buso_new_bu")
    with col2:
        new_short = st.text_input("Short Name", key="buso_new_short")
    col3, col4 = st.columns(2)
    with col3:
        new_group = st.text_input("Group", key="buso_new_group")
    with col4:
        new_sort = st.number_input("Sort Order", value=0, step=1, key="buso_new_sort")

    if st.button("Add Record", type="primary", key="buso_add"):
        if not all([new_bu, new_short, new_group]):
            st.error("Business Unit, Short Name, and Group are required.")
        else:
            new_id = str(uuid.uuid4())
            evt = {
                "ID": new_id,
                "Business Unit": new_bu,
                "Short Name": new_short,
                "Group": new_group,
                "Sort Order": new_sort,
                "Enabled": True,
            }
            write_events([evt])
            st.cache_data.clear()
            st.success(f"Added record: {new_id}. Refresh to see updates.")
