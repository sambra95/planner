"""Archive: the projects retired, and the history itself. A week is opened and
reviewed on My Week, which any of them can be picked on."""

from datetime import date

import streamlit as st

import db
import projectcard
from palette import NO_PROJECT

st.markdown("**Archived projects**")

projects = db.projects()
retired = projects[projects["archived"] == 1]
if retired.empty:
    st.caption("None archived.")
# Retiring a project hides none of what it held: the chip opens the same card
# as on Projects, with the way back where its archive and delete buttons are.
projectcard.chips(retired, "retired", [NO_PROJECT] + list(projects["name"]))

st.divider()
st.markdown("**Backups**")

outcome = st.session_state.pop("restored", None)
if outcome:
    st.success(outcome)

# One row: the button sizes to its label and the uploader takes the rest.
with st.container(horizontal=True, vertical_alignment="center"):
    st.download_button("Backup history", data=db.snapshot,
                       file_name=f"planner_backup_{date.today():%d%m%y}.db",
                       mime="application/vnd.sqlite3", icon=":material/download:",
                       help="Your whole history, as one file.")
    restoring = st.file_uploader("Restore history", type=["db"],
                                 label_visibility="collapsed",
                                 help="A file saved by Backup history.")

if restoring is not None:
    how = st.segmented_control("How to apply it", ["Merge", "Overwrite"],
                               default="Merge", label_visibility="collapsed")
    with st.popover(f"{how} this history", icon=":material/upload:"):
        if how == "Overwrite":
            st.markdown("**Replace everything with this file?**")
            st.caption("Every task, day, project and review in the app is written "
                       "over. This cannot be undone, so back up first.")
        else:
            st.markdown("**Add what is missing from this file?**")
            st.caption("Nothing here is changed or removed. A task, meeting or "
                       "paper of the same kind, title and day is already here, "
                       "so it is left alone.")
        if st.button("Yes, go ahead", type="primary"):
            try:
                if how == "Overwrite":
                    db.restore(restoring.getvalue())
                    outcome = "History replaced."
                else:
                    added = db.merge(restoring.getvalue())
                    outcome = ("Added " + ", ".join(f"{count} {name}"
                                                    for name, count in added.items())
                               if added else "Nothing to add: it is all here already.")
            except ValueError as problem:
                st.error(str(problem))
            else:
                # The message has to outlive the rerun that redraws the page.
                st.session_state["restored"] = outcome
                st.rerun()
