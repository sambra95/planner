"""One project's card: what it is, what it amounts to, and a searchable table
of everything assigned to it. A project is a chip like a task or a meeting, and
this is what opens when one is clicked - on Projects, and in the archive, where
retiring a project hides none of what it held.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import db

#: The kinds a project can hold, each with what finishing one is called: a
#: paper is read, the rest are completed.
KINDS = ((db.TASK, "Tasks", "completed"), (db.MEETING, "Meetings", "completed"),
         (db.PAPER, "Papers", "read"))

#: What finishing one of each kind is called, for a row's status.
FINISHED = {kind: verb for kind, _label, verb in KINDS}


def assigned(items: pd.DataFrame) -> dict:
    """Everything grouped by the project it belongs to, so a page drawing one
    card per project counts the rows once rather than once each."""
    return {name: frame for name, frame in items.groupby("project")}


def tally(project, mine: dict) -> None:
    """How much is attached, by kind and by whether it is finished. Counted from
    the rows already fetched for the search boxes, so this costs no query."""
    found = mine.get(project.name)
    finished = open_now = pd.Series(dtype=int)
    if found is not None:
        finished = found[found["done_on"].notna()]["kind"].value_counts()
        open_now = found[found["done_on"].isna()]["kind"].value_counts()
    st.markdown(" ".join(
        f":gray-badge[{label}: {int(open_now.get(kind, 0))} open, "
        f"{int(finished.get(kind, 0))} {verb}]" for kind, label, verb in KINDS))


def belongings(project, mine: dict, prefix: str):
    """Everything assigned to this project, in a table that stays one height
    however much there is. The box above it narrows the table, and picking a row
    gives that item back, for the caller to open in the editor its own page uses.
    `prefix` keeps two of these apart when both are on screen."""
    term = st.text_input(
        "Search", key=f"{prefix}search:{project.id}", label_visibility="collapsed",
        placeholder="Search this project's tasks, meetings and papers…")

    found = mine.get(project.name)
    if found is None:
        st.caption("Nothing assigned yet.")
        return None
    if term:
        found = found[found["haystack"].str.contains(term.strip().lower(),
                                                     regex=False, na=False)]
    if found.empty:
        st.caption("Nothing matching.")
        return None

    listing = pd.DataFrame({
        "Kind": found["kind"].str.capitalize(),
        "Item": found["title"],
        "Day": found["on_day"],
        "Status": [FINISHED[kind].capitalize() if pd.notna(done) else "Open"
                   for kind, done in zip(found["kind"], found["done_on"])],
        "Notes": found["notes"].fillna(""),
    })
    picked = st.dataframe(
        listing, hide_index=True, width="stretch", height=200,
        key=f"{prefix}hits:{project.id}", on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Kind": st.column_config.TextColumn(width="small"),
            "Item": st.column_config.TextColumn(width="large"),
            "Day": st.column_config.DateColumn(format="ddd DD MMM YYYY"),
            "Status": st.column_config.TextColumn(width="small"),
            "Notes": st.column_config.TextColumn(width="medium"),
        })

    # A selection outlives the dialog it opened, and every project keeps its
    # own, so opening on "something is selected" would reopen a stale row the
    # moment any dialog closed. Open only when this table's pick changes.
    rows = picked.selection.rows
    # One row, as a namedtuple: a dialog is a fragment and is handed its
    # arguments back on every rerun, and a Series does not survive that.
    chosen = next(found.iloc[[rows[0]]].itertuples()) if rows else None
    seen = f"{prefix}seen:{project.id}"
    if (chosen.id if chosen else None) == st.session_state.get(seen):
        return None
    st.session_state[seen] = chosen.id if chosen else None
    return chosen


def _rename(prefix: str, project_id: int) -> None:
    db.rename_project(project_id, st.session_state[f"{prefix}name:{project_id}"])


def _set_description(prefix: str, project_id: int) -> None:
    db.set_project_description(
        project_id, st.session_state[f"{prefix}about:{project_id}"])


def _set_dates(prefix: str, project_id: int) -> None:
    db.set_project_dates(project_id,
                         st.session_state[f"{prefix}start:{project_id}"],
                         st.session_state[f"{prefix}end:{project_id}"])


def _actions(project, prefix: str) -> None:
    """What can be done with the whole project. An archived one offers only the
    way back; a live one asks before either of the two that cannot be taken
    back lightly."""
    if project.archived:
        if st.button("Put it back", icon=":material/unarchive:",
                     key=f"{prefix}restore:{project.id}",
                     help="With a colour of its own again"):
            db.restore_project(project.id)
            st.rerun(scope="app")
        return

    row = st.columns(2)
    # Archiving takes the colour off everything assigned to it, so it asks
    # first, the way calling off a meeting does.
    with row[0].popover("Archive this project", icon=":material/archive:"):
        st.markdown(f"**Archive {project.name}?**")
        st.caption("It and everything assigned to it turn grey, and its colour "
                   "goes back into circulation. It moves to the Archive page, "
                   "and you can restore it from there.")
        if st.button("Yes, archive it", type="primary",
                     key=f"{prefix}archive:{project.id}"):
            db.archive_project(project.id)
            st.rerun(scope="app")
    # Deleting cannot be undone, so it asks first the way archiving does.
    with row[1].popover("Delete this project", icon=":material/delete:"):
        st.markdown(f"**Delete {project.name}?**")
        st.caption("Everything assigned to it is kept and simply shows as "
                   "having no project, and its colour goes back into "
                   "circulation. Archive it instead to keep the grouping. "
                   "This cannot be undone.")
        if st.button("Yes, delete it", type="primary",
                     key=f"{prefix}drop:{project.id}"):
            db.delete_project(project.id)
            st.rerun(scope="app")


def card(project, mine: dict, prefix: str) -> None:
    """Everything about one project, laid out as an item's own card is: the name
    on its own, then the dates, then what it holds."""
    if project.archived:
        st.markdown(":gray-badge[Archived]")
    st.text_input("Project", value=project.name, key=f"{prefix}name:{project.id}",
                  on_change=_rename, args=(prefix, project.id))

    # Either end may be left open, so both boxes start empty.
    span = st.columns(2)
    for column, field, label in ((span[0], "start_on", "From"),
                                 (span[1], "end_on", "To")):
        stamp = getattr(project, field)
        column.date_input(label, value=None if pd.isna(stamp) else stamp.date(),
                          key=f"{prefix}{field.split('_')[0]}:{project.id}",
                          format="DD/MM/YYYY", on_change=_set_dates,
                          args=(prefix, project.id))

    st.text_input("Description", key=f"{prefix}about:{project.id}",
                  value="" if pd.isna(project.description) else project.description,
                  placeholder="Add a description…",
                  on_change=_set_description, args=(prefix, project.id))

    tally(project, mine)
    picked = belongings(project, mine, prefix)
    if picked is not None:
        # One dialog cannot open another, so the page is left to do it: this
        # rerun closes this card, and the page finds the item waiting.
        st.session_state["project_item"] = picked
        st.rerun(scope="app")

    _actions(project, prefix)


@st.dialog("Project", width="large")
def open_project(project, mine: dict, prefix: str) -> None:
    """The card for one project. Public, because Projects and the archive open
    the same one."""
    card(project, mine, prefix)
