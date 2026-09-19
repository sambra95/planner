"""One day's card, and a week of them, shared by My Week and the archive.

The checklist is a tick and a name; description, milestones and notes open in a
dialog. Widget keys are prefixed per page so the same day rendered twice does
not collide in Session State.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
from palette import NO_PROJECT, chip_css, select_css, strike, style_block
from worktime import (DEFAULT_END, DEFAULT_START, clock, default_break,
                      WEEK_DAYS, field, is_holiday, net, or_default,
                      span, when)


def _save_day(prefix: str, day: date) -> None:
    holiday = st.session_state[f"{prefix}holiday:{day}"]
    db.save_day(day,
                None if holiday else st.session_state.get(f"{prefix}start:{day}"),
                None if holiday else st.session_state.get(f"{prefix}end:{day}"),
                None if holiday else st.session_state.get(f"{prefix}break:{day}"),
                st.session_state[f"{prefix}comment:{day}"], holiday)


def _toggle_task(prefix: str, task_id: int, day: date) -> None:
    """Ticking files it under this day; unticking puts it back."""
    done = st.session_state[f"{prefix}task:{task_id}"]
    db.set_task_done(task_id, day if done else None)


def _toggle_milestone(prefix: str, milestone_id: int) -> None:
    """A milestone stands alone: ticking it never finishes the task above it."""
    db.set_milestone_done(
        milestone_id, st.session_state[f"{prefix}dmilestone:{milestone_id}"])


def _clear_day(task_id: int) -> None:
    """Take something off this day without deleting it."""
    db.set_task_day(task_id, None)


def _rename(prefix: str, task_id: int) -> None:
    db.rename_task(task_id, st.session_state[f"{prefix}dtitle:{task_id}"])


def _move(prefix: str, task_id: int, kind: str) -> None:
    """Send it to another day. A meeting must keep one; a task or paper need
    not."""
    chosen = st.session_state[f"{prefix}dday:{task_id}"]
    if kind == db.MEETING:
        if chosen:
            db.move_meeting(task_id, chosen)
    else:
        db.set_task_day(task_id, chosen)


def _set_project(prefix: str, task_id: int) -> None:
    chosen = st.session_state[f"{prefix}dproject:{task_id}"]
    db.set_task_project(task_id, None if chosen == NO_PROJECT else chosen)


def _set_description(prefix: str, task_id: int) -> None:
    db.set_task_description(task_id, st.session_state[f"{prefix}dabout:{task_id}"])


def _set_times(prefix: str, task_id: int) -> None:
    db.set_meeting_times(task_id,
                         st.session_state[f"{prefix}dstart:{task_id}"],
                         st.session_state[f"{prefix}dend:{task_id}"])


def _set_tags(prefix: str, task_id: int) -> None:
    key = f"{prefix}dtags:{task_id}"
    st.session_state[key] = db.set_task_tags(task_id, st.session_state[key])


def _set_note(prefix: str, task_id: int, field: str) -> None:
    db.set_task_note(task_id, field,
                     st.session_state[f"{prefix}d{field}:{task_id}"])


def _add_milestone(prefix: str, task_id: int) -> None:
    db.add_milestone(task_id, st.session_state[f"{prefix}dnewmilestone:{task_id}"])
    st.session_state[f"{prefix}dnewmilestone:{task_id}"] = ""


#: How many milestones a card shows before the list starts scrolling, and what
#: one row of it stands. The height is a little over the rows shown, so the next
#: one peeks out and says there is more below.
_MILESTONES_SHOWN = 5
_MILESTONE_ROW = 42


def _milestone_box(count: int):
    """The frame the milestones are listed in. A short list simply takes the room
    it needs; a long one is capped and scrolls inside the card, so the box to add
    one and the buttons under it stay where they are."""
    if count <= _MILESTONES_SHOWN:
        return st.container()
    return st.container(
        height=_MILESTONES_SHOWN * _MILESTONE_ROW + _MILESTONE_ROW // 2)


#: What a meeting is written up under. A paper just has the one box.
_MEETING_SECTIONS = (("goals", "Goals"), ("notes", "Notes"),
                     ("actions", "Action points"))

def _draft_milestone(key: str) -> None:
    """Hold a milestone for a task that does not exist yet. It is written when
    the task is, so closing the box leaves no orphans behind."""
    if title := st.session_state[key + "newmilestone"].strip():
        st.session_state[key + "milestones"].append(title)
    st.session_state[key + "newmilestone"] = ""


def _paint_project(key: str, chosen: str | None) -> None:
    """Show the project box in its project's own colour. Read from the box
    rather than the item: a dialog keeps the arguments it opened with, so the
    item's colour would not follow a change made here."""
    if not chosen or chosen == NO_PROJECT:
        return
    colours = db.projects().set_index("name")["colour"]
    if chosen in colours.index:
        st.html(style_block([select_css(key, colours[chosen])]))


def _dismiss() -> None:
    """Remember what was closed. A table's selection outlives the dialog it
    opened, so without this the dialog reopens the moment it is dismissed; a
    chip does not need it, being a button that fires once."""
    st.session_state["dismissed_item"] = st.session_state.get("open_item")


def _editor(item, prefix: str, names: list[str]) -> None:
    """Everything about one item, and everything you can change about it."""
    st.session_state["open_item"] = item.id
    if pd.isna(item.done_on):
        st.markdown(f":gray-badge[Open {item.kind}]")
    else:
        # A paper is read, not quite "done".
        verb = "Read" if item.kind == db.PAPER else "Completed"
        st.markdown(f":green-badge[{verb} {item.done_on:%a %d %b %Y}]")

    # Laid out as the empty editor a new one is made in: the title on its own,
    # then project and day, and for a meeting the hours beside them.
    st.text_input("Title", value=item.title, key=f"{prefix}dtitle:{item.id}",
                  on_change=_rename, args=(prefix, item.id))
    if item.kind == db.MEETING:
        filed, dated, from_at, to_at = st.columns([3, 1, 1, 1])
    else:
        filed, dated = st.columns(2)

    project_key = f"{prefix}dproject:{item.id}"
    filed.selectbox("Project", names, key=project_key,
                    index=names.index(item.project)
                    if item.project in names else 0,
                    on_change=_set_project, args=(prefix, item.id))
    _paint_project(project_key, st.session_state.get(project_key, item.project))
    dated.date_input("Day", value=None if pd.isna(item.on_day)
                     else item.on_day.date(),
                     key=f"{prefix}dday:{item.id}", format="DD/MM/YYYY",
                     on_change=_move, args=(prefix, item.id, item.kind))

    # Only a task carries one: a meeting and a paper say what they are in their
    # write-up and their notes.
    if item.kind == db.TASK:
        st.text_input("Description", key=f"{prefix}dabout:{item.id}",
                      value="" if pd.isna(item.description) else item.description,
                      placeholder="Add a description…",
                      on_change=_set_description, args=(prefix, item.id))

    if item.kind == db.TASK:
        st.markdown("**Milestones**")
        # Read again rather than trusting the frame the dialog opened with: a
        # dialog is a fragment and is handed its arguments back on every rerun,
        # so adding or dropping one would not show until the page ran again.
        own = db.task_milestones(item.id)
        with _milestone_box(len(own)):
            for milestone in own.itertuples():
                row = st.columns([9, 0.6], vertical_alignment="center")
                row[0].checkbox(strike(milestone.title, bool(milestone.done)),
                                value=bool(milestone.done),
                                key=f"{prefix}dmilestone:{milestone.id}",
                                on_change=_toggle_milestone,
                                args=(prefix, milestone.id))
                row[1].button("", icon=":material/close:",
                              key=f"{prefix}ddropmilestone:{milestone.id}",
                              on_click=db.delete_milestone, args=(milestone.id,))
        st.text_input("New milestone", key=f"{prefix}dnewmilestone:{item.id}",
                      placeholder="Add a milestone…",
                      label_visibility="collapsed",
                      on_change=_add_milestone, args=(prefix, item.id))
    elif item.kind == db.MEETING:
        from_at.time_input("From", clock(item.start_time), step=900,
                           key=f"{prefix}dstart:{item.id}", on_change=_set_times,
                           args=(prefix, item.id))
        to_at.time_input("To", clock(item.end_time), step=900,
                         key=f"{prefix}dend:{item.id}", on_change=_set_times,
                         args=(prefix, item.id))
        for field, label in _MEETING_SECTIONS:
            st.text_area(label, key=f"{prefix}d{field}:{item.id}", height=130,
                         value="" if pd.isna(getattr(item, field))
                         else getattr(item, field),
                         placeholder=f"{label}…", on_change=_set_note,
                         args=(prefix, item.id, field))
    else:
        st.text_input("Tags", key=f"{prefix}dtags:{item.id}",
                      value="" if pd.isna(getattr(item, "tags", None))
                      else item.tags,
                      placeholder="Keywords, separated by commas…",
                      on_change=_set_tags, args=(prefix, item.id))
        st.text_area("Notes", key=f"{prefix}dnotes:{item.id}", height=180,
                     value="" if pd.isna(item.notes) else item.notes,
                     on_change=_set_note, args=(prefix, item.id, "notes"))

    if item.kind == db.MEETING:
        # A meeting only exists on its day, so taking it off the day deletes it.
        held = not pd.isna(item.done_on)
        wording = "Delete this meeting" if held else "Call off this meeting"
        with st.popover(wording, icon=":material/delete:"):
            st.markdown(f"**{wording}?**")
            st.caption("It goes, minutes and all. This cannot be undone.")
            if st.button("Yes, delete it" if held else "Yes, call it off",
                         type="primary", key=f"{prefix}ddrop:{item.id}"):
                db.delete_task(item.id)
                st.rerun(scope="app")
    elif pd.isna(item.done_on) and not pd.isna(item.day):
        # Only worth offering when it is on a day to be taken off.
        if st.button("Take off this day", icon=":material/event_busy:",
                     key=f"{prefix}dclear:{item.id}"):
            _clear_day(item.id)
            st.rerun(scope="app")
    elif not pd.isna(item.done_on):
        # Finished, but not really: this puts it back where it came from, the
        # day it was filed under along with it.
        back = ("reading list" if item.kind == db.PAPER else "task list")
        if st.button(f"Put back on the {back}", icon=":material/undo:",
                     key=f"{prefix}dundo:{item.id}"):
            db.set_task_done(item.id, None)
            st.rerun(scope="app")


#: What each kind is called where a new one is being made.
_KIND_NAMES = {db.TASK: "task", db.MEETING: "meeting", db.PAPER: "paper"}


@st.dialog("Add task", width="large")
def _new_task(kind, names, day):
    _new(kind, names, day)


@st.dialog("Add meeting", width="large")
def _new_meeting(kind, names, day):
    _new(kind, names, day)


@st.dialog("Add paper", width="large")
def _new_paper(kind, names, day):
    _new(kind, names, day)


def add_button(kind: str, names: list[str], day: date | None = None) -> None:
    """The button that opens an empty editor for a new item of `kind`. Opening
    it drops whatever was typed into a previous one and abandoned, so it always
    starts blank."""
    if st.button(f"Add {_KIND_NAMES[kind]}", icon=":material/add:",
                 width="stretch", key=f"open_new_{kind}"):
        forget_draft(f"new_{kind}_")
        {db.TASK: _new_task, db.MEETING: _new_meeting,
         db.PAPER: _new_paper}[kind](kind, names, day)


def forget_draft(prefix: str) -> None:
    """Clear the fields of an editor for something that was never made. Safe
    here: the widgets it names belong to a run that is over."""
    for key in [key for key in st.session_state if key.startswith(prefix)]:
        del st.session_state[key]


def _new(kind: str, names: list[str], day: date | None) -> None:
    """A new item of `kind`, laid out like the editor that opens on an existing
    one but with every field empty. Nothing is written until Add is pressed, so
    a half-filled box that is closed leaves nothing behind."""
    what = _KIND_NAMES[kind]
    key = f"new_{kind}_"

    # The title on its own, then project and day, and for a meeting the hours
    # beside them, so every kind reads the same way.
    title = st.text_input("Title", key=key + "title", placeholder=f"The {what}…")
    if kind == db.MEETING:
        filed, dated, from_at, to_at = st.columns([3, 1, 1, 1])
    else:
        filed, dated = st.columns(2)

    project = filed.selectbox("Project", names, key=key + "project")
    _paint_project(key + "project", project)
    # A meeting lives on its day, so it starts on one rather than nowhere.
    when = dated.date_input("Day", value=day, key=key + "day",
                            format="DD/MM/YYYY")
    description = ("" if kind != db.TASK else
                   st.text_input("Description", key=key + "about",
                                 placeholder="Add a description…"))

    times, notes = (None, None), {}
    if kind == db.MEETING:
        times = (from_at.time_input("From", value=None, step=900,
                                    key=key + "start"),
                 to_at.time_input("To", value=None, step=900, key=key + "end"))
        for field, label in _MEETING_SECTIONS:
            notes[field] = st.text_area(label, height=130, key=key + field,
                                        placeholder=f"{label}…")
    elif kind == db.PAPER:
        tags = st.text_input("Tags", key=key + "tags",
                             placeholder="Keywords, separated by commas…")
        notes["notes"] = st.text_area("Notes", height=180, key=key + "notes")
    elif kind == db.TASK:
        st.markdown("**Milestones**")
        drafted = st.session_state.setdefault(key + "milestones", [])
        with _milestone_box(len(drafted)):
            for index, milestone in enumerate(drafted):
                row = st.columns([9, 0.6], vertical_alignment="center")
                row[0].markdown(milestone)
                row[1].button("", icon=":material/close:",
                              key=f"{key}dropmilestone:{index}",
                              on_click=drafted.pop, args=(index,))
        st.text_input("New milestone", key=key + "newmilestone",
                      placeholder="Add a milestone…",
                      label_visibility="collapsed", on_change=_draft_milestone,
                      args=(key,))

    if not st.button(f"Add {what}", type="primary", width="stretch",
                     key=key + "submit"):
        return
    if not title.strip():
        st.error("A title is needed. Everything else can wait.")
        return

    # Made first, then filled in: the setters the editor uses take an id.
    new_id = (db.add_meeting(title, when) if kind == db.MEETING
              else db.add_paper(title, when) if kind == db.PAPER
              else db.add_task(title))
    if kind == db.TASK and when:
        db.set_task_day(new_id, when)
    if project != NO_PROJECT:
        db.set_task_project(new_id, project)
    if description.strip():
        db.set_task_description(new_id, description)
    if kind == db.MEETING and any(times):
        db.set_meeting_times(new_id, *times)
    if kind == db.PAPER and tags.strip():
        db.set_task_tags(new_id, tags)
    for field, written in notes.items():
        if written.strip():
            db.set_task_note(new_id, field, written)
    for milestone in st.session_state.get(key + "milestones", []):
        db.add_milestone(new_id, milestone)
    st.rerun(scope="app")


#: A dialog takes its title when it is decorated, so each kind gets its own.
@st.dialog("Task", width="large", on_dismiss=_dismiss)
def _open_task(item, prefix, names):
    _editor(item, prefix, names)


@st.dialog("Meeting", width="large", on_dismiss=_dismiss)
def _open_meeting(item, prefix, names):
    _editor(item, prefix, names)


@st.dialog("Paper", width="large", on_dismiss=_dismiss)
def _open_paper(item, prefix, names):
    _editor(item, prefix, names)


def open_item(item, prefix: str, names: list[str]) -> None:
    """The editor for one item, titled with what it is. Public, because every
    page that lists items opens the same one."""
    opener = {db.TASK: _open_task, db.MEETING: _open_meeting,
              db.PAPER: _open_paper}[item.kind]
    opener(item, prefix, names)


def render_day(day: date, record, tasks: pd.DataFrame,
               milestones: pd.DataFrame, prefix: str, rules: list[str]):
    """One day's card. Returns the item whose name was clicked, if any."""
    opened = None
    with st.container(border=True):
        header = st.columns([3, 2], vertical_alignment="center")
        header[0].markdown(f"**{day:%a %-d %b}**"
                           + (" :blue-badge[today]" if day == date.today() else ""))
        away = header[1].checkbox("Holiday", value=is_holiday(record),
                                  key=f"{prefix}holiday:{day}",
                                  help="Leave this day out of every time "
                                       "calculation.",
                                  on_change=_save_day, args=(prefix, day))

        if away:
            st.caption("Holiday - not counted.")
        else:
            # Only a weekday stands in as an ordinary day; a weekend default
            # would read as unearned overtime.
            ordinary = day.weekday() < WEEK_DAYS
            clocks = st.columns(2)
            start = clocks[0].time_input(
                "Start", or_default(clock(field(record, "start_time")),
                                    DEFAULT_START if ordinary else None),
                step=900, key=f"{prefix}start:{day}", on_change=_save_day,
                args=(prefix, day))
            end = clocks[1].time_input(
                "End", or_default(clock(field(record, "end_time")),
                                  DEFAULT_END if ordinary else None),
                step=900, key=f"{prefix}end:{day}", on_change=_save_day,
                args=(prefix, day))
            st.number_input(
                "Break", min_value=0.0, max_value=24.0, step=0.5,
                value=or_default(field(record, "break_hours"),
                                 default_break() if ordinary else None),
                key=f"{prefix}break:{day}",
                help="Hours between start and end that were not work. They come "
                     "off the hours worked.",
                on_change=_save_day, args=(prefix, day))

            hours = net(span(start, end),
                        st.session_state.get(f"{prefix}break:{day}"))
            st.caption(f"{round(hours, 2):g} h worked" if hours is not None
                       else "No hours yet")

        for item in tasks.itertuples():
            done = not pd.isna(item.done_on)
            own = (milestones[milestones["task_id"] == item.id]
                   if item.kind == db.TASK else milestones.iloc[0:0])
            tally = f" ({int(own['done'].sum())}/{len(own)})" if len(own) else ""
            if not pd.isna(item.colour):
                rules.append(chip_css(f"{prefix}open:{item.id}", item.colour))

            line = st.columns([1, 7], vertical_alignment="center")
            line[0].checkbox("Done", value=done, key=f"{prefix}task:{item.id}",
                             label_visibility="collapsed",
                             on_change=_toggle_task, args=(prefix, item.id, day))
            clock_face = when(item._asdict()) if item.kind == db.MEETING else ""
            label_text = f"{clock_face} {strike(item.title, done)}".strip()
            if line[1].button(label_text + tally,
                              key=f"{prefix}open:{item.id}", width="stretch"):
                opened = item

        if tasks.empty:
            st.caption("No tasks assigned.")

        st.text_area("Notes", value=field(record, "comment") or "", height=80,
                     key=f"{prefix}comment:{day}", on_change=_save_day,
                     args=(prefix, day))
    return opened


def render_week(week_start: date, records: dict, tasks: pd.DataFrame,
                milestones: pd.DataFrame, prefix: str = "") -> None:
    """Monday to Friday side by side, with the weekend in an expander."""
    opened, rules = None, []

    def card(day: date):
        return render_day(day, records.get(day, {}),
                          tasks[tasks["on_day"] == pd.Timestamp(day)],
                          milestones, prefix, rules)

    for column, offset in zip(st.columns(5), range(5)):
        with column:
            opened = card(week_start + timedelta(days=offset)) or opened

    with st.expander("Weekend", icon=":material/weekend:"):
        for column, offset in zip(st.columns(2), (5, 6)):
            with column:
                opened = card(week_start + timedelta(days=offset)) or opened

    if rules:
        st.html(style_block(rules))
    if opened is not None:
        open_item(opened, prefix, [NO_PROJECT] + list(db.projects()["name"]))
