"""Projects: a name, an optional description, dates and a colour of its own.
One chip each, as a task or a meeting is, opening the project's own card.
Archived ones live in the Archive."""

import streamlit as st

import daycard
import db
import projectcard
from palette import NO_PROJECT, chip_css, style_block


@st.dialog("Add project", width="large")
def _add_project() -> None:
    """A new project, laid out like the card it will become but empty. Its
    colour is not asked for: the next unused one is handed out."""
    name = st.text_input("Project", key="new_pname", placeholder="The project…")
    about = st.text_input("Description", key="new_pabout",
                          placeholder="Add a description…")
    span = st.columns(2)
    start = span[0].date_input("From", value=None, key="new_pstart",
                               format="DD/MM/YYYY")
    end = span[1].date_input("To", value=None, key="new_pend", format="DD/MM/YYYY")

    if not st.button("Add project", type="primary", width="stretch",
                     key="new_psubmit"):
        return
    if not name.strip():
        st.error("A name is needed. Everything else can wait.")
        return
    new_id = db.add_project(name)
    if about.strip():
        db.set_project_description(new_id, about)
    if start or end:
        db.set_project_dates(new_id, start, end)
    st.rerun(scope="app")


if st.button("Add project", icon=":material/add:", width="stretch"):
    daycard.forget_draft("new_p")
    _add_project()

projects = db.projects()
live = projects[projects["archived"] == 0]
mine = projectcard.assigned(db.project_items())
names = [NO_PROJECT] + list(live["name"])

# Stashed by a project's card: one dialog cannot open another, so the item a
# card's table picked is opened here instead.
picked = st.session_state.pop("project_item", None)

if live.empty:
    st.caption("No projects yet.")

rules = []
for project in live.itertuples():
    rules.append(chip_css(f"project:{project.id}", project.colour))
    if st.button(project.name, key=f"project:{project.id}", width="stretch"):
        projectcard.open_project(project, mine, "p")

# One style block for every chip, each in its project's colour.
if rules:
    st.html(style_block(rules))

if picked is not None:
    daycard.open_item(picked, "proj:", names)
