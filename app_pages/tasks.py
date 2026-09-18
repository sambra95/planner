"""Open tasks: one editable table. Add a row to plan something, set its day to
put it in the week view, tick it off when it is done."""

import streamlit as st

import db

st.subheader("Open tasks", anchor=False)
st.caption("Add a task, give it a day, and it appears in that day's checklist. "
           "Anything still open after its day comes back here as pushed forward.")

frame = db.open_tasks()

# A fresh key after every save, so the editor starts from the saved rows.
key = f"tasks_editor_{st.session_state.get('tasks_revision', 0)}"
st.data_editor(
    frame, key=key, width="stretch", hide_index=True, num_rows="dynamic",
    column_config={
        "id": None,
        "done": st.column_config.CheckboxColumn("Done", width="small", default=False),
        "title": st.column_config.TextColumn("Task", width="large", required=True),
        "day": st.column_config.DateColumn("Day", width="small", format="ddd DD MMM"),
        "status": st.column_config.TextColumn("", width="small", disabled=True),
    })

delta = st.session_state[key]
if any(delta.values()):
    db.save_task_edits(delta, frame)
    st.session_state["tasks_revision"] = st.session_state.get("tasks_revision", 0) + 1
    st.rerun()

if frame.empty:
    st.caption("Nothing open.")
else:
    pushed = int((frame["status"] != "").sum())
    st.caption(f"{len(frame)} open"
               + (f" · {pushed} pushed forward" if pushed else ""))
