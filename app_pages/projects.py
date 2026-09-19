"""Projects: a name, an optional description, dates and a colour of its own.
One card each, laid out like the task list. Archived ones live in the Archive."""

import pandas as pd
import streamlit as st

import daycard
import db
from palette import NO_PROJECT, card_css, style_block


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


def _rename(project_id: int) -> None:
    db.rename_project(project_id, st.session_state[f"pname:{project_id}"])


def _set_description(project_id: int) -> None:
    db.set_project_description(project_id, st.session_state[f"pabout:{project_id}"])


def _set_dates(project_id: int) -> None:
    db.set_project_dates(project_id, st.session_state[f"pstart:{project_id}"],
                         st.session_state[f"pend:{project_id}"])


if st.button("Add project", icon=":material/add:", width="stretch"):
    daycard.forget_draft("new_p")
    _add_project()

projects = db.projects()
live = projects[projects["archived"] == 0]
items = db.project_items()
mine = {name: frame for name, frame in items.groupby("project")}
names = [NO_PROJECT] + list(live["name"])
rules = []
opened = None


#: The kinds a project can hold, each with what finishing one is called: a
#: paper is read, the rest are completed.
KINDS = ((db.TASK, "Tasks", "completed"), (db.MEETING, "Meetings", "completed"),
         (db.PAPER, "Papers", "read"))

#: What finishing one of each kind is called, for a row's status.
FINISHED = {kind: verb for kind, _label, verb in KINDS}


def _tally(project) -> None:
    """How much is attached, by kind and by whether it is finished. Counted from
    the rows already fetched for the search boxes, so this costs no query."""
    found = mine.get(project.name)
    if found is None:
        found = items.iloc[0:0]
    finished = found[found["done_on"].notna()]["kind"].value_counts()
    open_now = found[found["done_on"].isna()]["kind"].value_counts()
    st.markdown(" ".join(
        f":gray-badge[{label}: {int(open_now.get(kind, 0))} open, "
        f"{int(finished.get(kind, 0))} {verb}]" for kind, label, verb in KINDS))


def _belongings(project) -> None:
    """Everything assigned to this project, in a table that stays one height
    however much there is. The box above it narrows the table, and picking a row
    opens the same editor the item's own page uses."""
    global opened
    term = st.text_input(
        "Search", key=f"psearch:{project.id}", label_visibility="collapsed",
        placeholder="Search this project's tasks, meetings and papers…")

    found = mine.get(project.name)
    if found is None:
        st.caption("Nothing assigned yet.")
        return
    if term:
        found = found[found["haystack"].str.contains(term.strip().lower(),
                                                     regex=False, na=False)]
    if found.empty:
        st.caption("Nothing matching.")
        return

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
        key=f"phits:{project.id}", on_select="rerun", selection_mode="single-row",
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
    seen = f"pseen:{project.id}"
    if (chosen.id if chosen else None) != st.session_state.get(seen):
        st.session_state[seen] = chosen.id if chosen else None
        if chosen is not None and opened is None:
            opened = chosen


def _card(project) -> None:
    """One project card."""
    rules.append(card_css(f"project-{project.id}", project.colour))
    with st.container(border=True, key=f"project-{project.id}"):
        head = st.columns([7.4, 0.5, 0.5], vertical_alignment="center")
        head[0].text_input("Project", value=project.name, key=f"pname:{project.id}",
                           label_visibility="collapsed", on_change=_rename,
                           args=(project.id,))
        # Archiving takes the colour off everything assigned to it, so it asks
        # first, the way calling off a meeting does.
        with head[1].popover("", icon=":material/archive:"):
            st.markdown(f"**Archive {project.name}?**")
            st.caption("It and everything assigned to it turn grey, and its "
                       "colour goes back into circulation. It moves to the "
                       "Archive page, and you can restore it from there.")
            if st.button("Yes, archive it", type="primary",
                         key=f"parchive:{project.id}"):
                db.archive_project(project.id)
                st.rerun()
        # Deleting cannot be undone, so it asks first the way archiving does.
        with head[2].popover("", icon=":material/delete:"):
            st.markdown(f"**Delete {project.name}?**")
            st.caption("Everything assigned to it is kept and simply shows as "
                       "having no project, and its colour goes back into "
                       "circulation. Archive it instead to keep the grouping. "
                       "This cannot be undone.")
            if st.button("Yes, delete it", type="primary",
                         key=f"pdrop:{project.id}"):
                db.delete_project(project.id)
                st.rerun()

        about = st.columns([5.8, 1.6, 1.6], vertical_alignment="center")
        about[0].text_input(
            "Description", key=f"pabout:{project.id}",
            value="" if pd.isna(project.description) else project.description,
            placeholder="Add a description…", label_visibility="collapsed",
            on_change=_set_description, args=(project.id,))
        # Either end may be left open, so both boxes start empty.
        for column, field, label in ((about[1], "start_on", "From"),
                                     (about[2], "end_on", "To")):
            stamp = getattr(project, field)
            column.date_input(
                label, value=None if pd.isna(stamp) else stamp.date(),
                key=f"p{field.split('_')[0]}:{project.id}", format="DD/MM/YYYY",
                on_change=_set_dates, args=(project.id,))

        _tally(project)
        _belongings(project)


if live.empty:
    st.caption("No projects yet.")
for project in live.itertuples():
    _card(project)

# One style block for every card, each in its project's colour.
if rules:
    st.html(style_block(rules))

if opened is not None:
    daycard.open_item(opened, "proj:", names)
