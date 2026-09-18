"""Projects: a name, an optional description, and a colour of its own. One card
each, laid out like the task list."""

import pandas as pd
import streamlit as st

import db
from palette import card_css


def _add_project() -> None:
    db.add_project(st.session_state["new_project"])
    st.session_state["new_project"] = ""


def _rename(project_id: int) -> None:
    db.rename_project(project_id, st.session_state[f"pname:{project_id}"])


def _set_description(project_id: int) -> None:
    db.set_project_description(project_id, st.session_state[f"pabout:{project_id}"])


st.subheader("Projects", anchor=False)
st.caption("Each project is given a colour of its own, automatically. Tasks "
           "assigned to it are badged with that colour wherever they appear. "
           "Archive one to retire it and hand its colour back.")

st.text_input("New project", key="new_project", placeholder="Add a project…",
              label_visibility="collapsed", on_change=_add_project)

projects = db.projects()
live = projects[projects["archived"] == 0]
retired = projects[projects["archived"] == 1]
rules = []


def _card(project, archived: bool) -> None:
    """One project card."""
    rules.append(card_css(f"project-{project.id}", project.colour))
    with st.container(border=True, key=f"project-{project.id}"):
        head = st.columns([7.4, 0.5, 0.5], vertical_alignment="center")
        head[0].text_input("Project", value=project.name, key=f"pname:{project.id}",
                           label_visibility="collapsed", on_change=_rename,
                           args=(project.id,))
        if archived:
            head[1].button("", icon=":material/unarchive:",
                           key=f"prestore:{project.id}",
                           on_click=db.restore_project, args=(project.id,))
        else:
            head[1].button("", icon=":material/archive:",
                           key=f"parchive:{project.id}",
                           on_click=db.archive_project, args=(project.id,))
        head[2].button("", icon=":material/delete:", key=f"pdrop:{project.id}",
                       on_click=db.delete_project, args=(project.id,))

        about = st.columns([0.6, 6, 3.4], vertical_alignment="center")
        about[1].text_input(
            "Description", key=f"pabout:{project.id}",
            value="" if pd.isna(project.description) else project.description,
            placeholder="Add a description…", label_visibility="collapsed",
            on_change=_set_description, args=(project.id,))


if live.empty:
    st.caption("No projects yet.")
for project in live.itertuples():
    _card(project, archived=False)

if not retired.empty:
    st.markdown("**Archived**")
    st.caption("Grey, along with everything still assigned to them. Their "
               "colours are back in circulation.")
    for project in retired.itertuples():
        _card(project, archived=True)

# One style block for every card, each in its project's colour.
if rules:
    st.html("<style>" + "\n".join(rules) + "</style>")
