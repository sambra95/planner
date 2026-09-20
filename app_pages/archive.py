"""Archive: the projects retired, and the history itself. A week is opened and
reviewed on My Week, which any of them can be picked on."""

from datetime import date

import streamlit as st

import daycard
import db
import projectcard
from palette import NO_PROJECT, chip_css, style_block

st.markdown("**Archived projects**")

projects = db.projects()
retired = projects[projects["archived"] == 1]
if retired.empty:
    st.caption("None archived.")
else:
    # Retiring a project does not hide what it held: the chip opens the same
    # card it has on the Projects page, with the way back where the archive and
    # delete buttons are there.
    mine = projectcard.assigned(db.project_items())

# Stashed by a project's card, which cannot open a dialog from inside one.
picked = st.session_state.pop("project_item", None)

rules = []
for project in retired.itertuples():
    rules.append(chip_css(f"retired:{project.id}", project.colour))
    if st.button(project.name, key=f"retired:{project.id}", width="stretch"):
        projectcard.open_project(project, mine, "arch")

if rules:
    st.html(style_block(rules))

if picked is not None:
    daycard.open_item(picked, "arch:", [NO_PROJECT] + list(projects["name"]))

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
