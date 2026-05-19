import streamlit as st
import pandas as pd
import json
import uuid

session = st.session_state["conn"].session()

# st.set_page_config(page_title="Balance Sheet Mapping Admin", layout="wide")
# st.title("Balance Sheet Mapping Admin")

@st.cache_data(ttl=600)
def load_master_data():
    df = session.sql("""
        SELECT
            "(PK) ID"           AS "ID",
            "BalanceSheet Entity",
            "Minimum GL Value",
            "Maximum GL Value",
            "Enabled",
            "Changed By",
            "Changed On"
        FROM CONFIG.SILVER."Balance_Sheet_Mapping_MasterData" WHERE "Enabled" = true 
        ORDER BY "BalanceSheet Entity", "Minimum GL Value"
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
            INSERT INTO CONFIG.RAW.BALANCE_SHEET_MAPPING_EVENTDATA
                (SERIALIZED_SOURCE, EVENT_TIME)
            SELECT
                PARSE_JSON('{payload.replace("'", "''")}'),
                CURRENT_TIMESTAMP()
        """).collect()

def find_overlaps(df, entity, gl_min, gl_max):
    entity_df = df[
        (df["BalanceSheet Entity"] == entity)
        & (df["Enabled"] == True)
    ]
    overlaps = entity_df[
        (entity_df["Minimum GL Value"] <= gl_max)
        & (entity_df["Maximum GL Value"] >= gl_min)
    ]
    return overlaps

master_df = load_master_data()

tab_edit, tab_add = st.tabs(["Edit Existing", "Add New"])

with tab_edit:
    st.caption("Edit rows below. Changes are saved as change events with full audit trail.")

    entity_filter = st.selectbox(
        "Filter by BalanceSheet Entity",
        options=["All"] + sorted(master_df["BalanceSheet Entity"].unique().tolist()),
        key="entity_filter",
    )

    if entity_filter == "All":
        filtered_df = master_df
    else:
        filtered_df = master_df[master_df["BalanceSheet Entity"] == entity_filter].reset_index(drop=True)

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
                    "BalanceSheet Entity": orig["BalanceSheet Entity"],
                    "Minimum GL Value": orig["Minimum GL Value"],
                    "Maximum GL Value": orig["Maximum GL Value"],
                    "Enabled": False,
                })
                continue

            curr_comparable = curr.drop("Delete")
            if not orig.equals(curr_comparable):
                gl_changed = (
                    orig["BalanceSheet Entity"] != curr["BalanceSheet Entity"]
                    or orig["Minimum GL Value"] != curr["Minimum GL Value"]
                    or orig["Maximum GL Value"] != curr["Maximum GL Value"]
                )
                if gl_changed and bool(curr["Enabled"]):
                    overlaps = find_overlaps(
                        master_df[master_df["ID"] != orig["ID"]],
                        curr["BalanceSheet Entity"],
                        curr["Minimum GL Value"],
                        curr["Maximum GL Value"],
                    )
                    if not overlaps.empty:
                        overlap_warnings.append((orig["ID"], curr, overlaps))

                changes.append({
                    "ID": orig["ID"],
                    "BalanceSheet Entity": curr["BalanceSheet Entity"],
                    "Minimum GL Value": curr["Minimum GL Value"],
                    "Maximum GL Value": curr["Maximum GL Value"],
                    "Enabled": bool(curr["Enabled"]),
                })

        if overlap_warnings:
            st.error(f"Found GL range overlaps in {len(overlap_warnings)} edit(s). Changes not saved.")
            for row_id, curr, overlaps in overlap_warnings:
                st.warning(
                    f"Row `{row_id}`: range `{curr['Minimum GL Value']}`-"
                    f"`{curr['Maximum GL Value']}` for Entity `{curr['BalanceSheet Entity']}` "
                    f"overlaps with:"
                )
                st.dataframe(
                    overlaps[["ID", "BalanceSheet Entity", "Minimum GL Value", "Maximum GL Value"]],
                    hide_index=True,
                    use_container_width=True,
                )
        elif changes:
            if deletes:
                st.warning(f"Disabling {len(deletes)} mapping(s): {', '.join(deletes)}")
            write_events(changes)
            st.cache_data.clear()
            st.success(f"Saved {len(changes)} event(s).")
            st.rerun()
        else:
            st.info("No changes detected.")
with tab_add:
    st.subheader("Add New Mapping")
    col1, col2, col3 = st.columns(3)
    with col1:
        new_entity = st.text_input("BalanceSheet Entity")
    with col2:
        new_min = st.text_input("Minimum GL Value")
    with col3:
        new_max = st.text_input("Maximum GL Value")

    if st.button("Add Mapping", type="primary"):
        if not all([new_entity, new_min, new_max]):
            st.error("All fields are required.")
        else:
            overlaps = find_overlaps(master_df, new_entity, new_min, new_max)
            if not overlaps.empty:
                st.error(
                    f"GL range `{new_min}`–`{new_max}` overlaps with "
                    f"{len(overlaps)} existing mapping(s) for Entity `{new_entity}`:"
                )
                st.dataframe(
                    overlaps[["ID", "Minimum GL Value", "Maximum GL Value"]],
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                new_id = str(uuid.uuid4())
                evt = {
                    "ID": new_id,
                    "BalanceSheet Entity": new_entity,
                    "Minimum GL Value": new_min,
                    "Maximum GL Value": new_max,
                    "Enabled": True,
                }
                write_events([evt])
                st.cache_data.clear()
                st.success(f"Added mapping: {new_id}")
                st.rerun()

