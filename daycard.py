"""One day's card, and a week of them, as the week view and the archive draw it.

Both pages show the same thing, so both build it from here: times, breaks,
that day's checklist and its comment, in a bordered card per day, Monday
to Friday across the page with the weekend folded away.

The checklist is kept to a tick and a name, in the item's project colour; its
description, steps and notes open in a dialog, the way a meeting does on the
Meetings page.

Widget keys are prefixed per page, so the same day rendered on two pages does not
collide in Session State.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
from palette import NO_PROJECT, chip_css, strike
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
    """Ticking files it under this day; unticking puts it back where it came
    from, which is how something ticked off by mistake is undone."""
    done = st.session_state[f"{prefix}task:{task_id}"]
    db.set_task_done(task_id, day if done else None)


def _toggle_step(prefix: str, step_id: int) -> None:
    """A step stands alone: ticking it never finishes the task above it."""
    db.set_step_done(step_id, st.session_state[f"{prefix}step:{step_id}"])


def _clear_day(task_id: int) -> None:
    """Take something off this day without deleting it: a task goes back to the
    open list, a paper back to the Papers page."""
    db.set_task_day(task_id, None)


def _rename(prefix: str, task_id: int) -> None:
    db.rename_task(task_id, st.session_state[f"{prefix}dtitle:{task_id}"])


def _move(prefix: str, task_id: int, kind: str) -> None:
    """Send it to another day. A meeting takes its record with it and must keep
    a day; a task or paper can simply be left undated."""
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


#: What a meeting is written up under. A paper just has the one box.
MEETING_SECTIONS = (("goals", "Goals"), ("notes", "Comments"),
                    ("actions", "Action points"))


def _set_times(prefix: str, task_id: int) -> None:
    db.set_meeting_times(task_id,
                         st.session_state[f"{prefix}dstart:{task_id}"],
                         st.session_state[f"{prefix}dend:{task_id}"])


def _set_note(prefix: str, task_id: int, field: str) -> None:
    db.set_task_note(task_id, field,
                     st.session_state[f"{prefix}d{field}:{task_id}"])


def _add_step(prefix: str, task_id: int) -> None:
    db.add_step(task_id, st.session_state[f"{prefix}dnewstep:{task_id}"])
    st.session_state[f"{prefix}dnewstep:{task_id}"] = ""


@st.dialog("On this day", width="large", on_dismiss="rerun")
def _open(item, steps: pd.DataFrame, prefix: str, names: list[str]) -> None:
    """Everything about one item, and everything you can change about it.

    A dialog is a fragment, so editing here reruns only the dialog and leaves it
    open; dismissing it reruns the page so the week catches up with a changed
    title or day.
    """
    st.text_input("Title", value=item.title, key=f"{prefix}dtitle:{item.id}",
                  on_change=_rename, args=(prefix, item.id))

    side = st.columns(2)
    side[0].date_input("Day", value=item.on_day.date(),
                       key=f"{prefix}dday:{item.id}", format="DD/MM/YYYY",
                       on_change=_move, args=(prefix, item.id, item.kind))
    side[1].selectbox("Project", names, key=f"{prefix}dproject:{item.id}",
                      index=names.index(item.project)
                      if item.project in names else 0,
                      on_change=_set_project, args=(prefix, item.id))

    st.text_input("Description", key=f"{prefix}dabout:{item.id}",
                  value="" if pd.isna(item.description) else item.description,
                  placeholder="Add a description…",
                  on_change=_set_description, args=(prefix, item.id))

    if item.kind == db.TASK:
        st.markdown("**Steps**")
        own = steps[steps["task_id"] == item.id]
        for step in own.itertuples():
            row = st.columns([9, 0.6], vertical_alignment="center")
            row[0].checkbox(strike(step.title, bool(step.done)),
                            value=bool(step.done), key=f"{prefix}dstep:{step.id}",
                            on_change=_toggle_step, args=(prefix, step.id))
            row[1].button("", icon=":material/close:",
                          key=f"{prefix}ddropstep:{step.id}",
                          on_click=db.delete_step, args=(step.id,))
        st.text_input("New step", key=f"{prefix}dnewstep:{item.id}",
                      placeholder="Add a step…", label_visibility="collapsed",
                      on_change=_add_step, args=(prefix, item.id))
    elif item.kind == db.MEETING:
        times = st.columns(2)
        times[0].time_input("From", clock(item.start_time), step=900,
                            key=f"{prefix}dstart:{item.id}", on_change=_set_times,
                            args=(prefix, item.id))
        times[1].time_input("To", clock(item.end_time), step=900,
                            key=f"{prefix}dend:{item.id}", on_change=_set_times,
                            args=(prefix, item.id))
        for field, label in MEETING_SECTIONS:
            st.text_area(label, key=f"{prefix}d{field}:{item.id}", height=130,
                         value="" if pd.isna(getattr(item, field))
                         else getattr(item, field),
                         placeholder=f"{label}…", on_change=_set_note,
                         args=(prefix, item.id, field))
    else:
        st.text_area("Comments", key=f"{prefix}dnotes:{item.id}", height=180,
                     value="" if pd.isna(item.notes) else item.notes,
                     on_change=_set_note, args=(prefix, item.id, "notes"))

    st.caption("Saved as you type.")

    if pd.isna(item.done_on) and item.kind == db.MEETING:
        # A meeting only exists on its day, so taking it off calls it off.
        with st.popover("Call off this meeting", icon=":material/delete:"):
            st.markdown("**Call off this meeting?**")
            st.caption("It is deleted, minutes and all.")
            if st.button("Yes, call it off", type="primary",
                         key=f"{prefix}ddrop:{item.id}"):
                db.delete_task(item.id)
                st.rerun(scope="app")
    elif pd.isna(item.done_on):
        if st.button("Take off this day", icon=":material/event_busy:",
                     key=f"{prefix}dclear:{item.id}"):
            _clear_day(item.id)
            st.rerun(scope="app")


def render_day(day: date, record, tasks: pd.DataFrame, steps: pd.DataFrame,
               prefix: str, rules: list[str]):
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
            st.caption("Holiday — not counted.")
        else:
            # Only a weekday stands in as an ordinary day. A weekend shows
            # what is on it and nothing more, because nothing is expected there
            # and a default would read as unearned overtime.
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
            own = (steps[steps["task_id"] == item.id] if item.kind == db.TASK
                   else steps.iloc[0:0])
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

        st.text_area("Comments", value=field(record, "comment") or "", height=80,
                     key=f"{prefix}comment:{day}", on_change=_save_day,
                     args=(prefix, day))
    return opened


def render_week(week_start: date, records: dict, tasks: pd.DataFrame,
                steps: pd.DataFrame, prefix: str = "") -> None:
    """Monday to Friday side by side, with the weekend in an expander."""
    opened, rules = None, []

    def card(day: date):
        return render_day(day, records.get(day, {}),
                          tasks[tasks["on_day"] == pd.Timestamp(day)], steps,
                          prefix, rules)

    for column, offset in zip(st.columns(5), range(5)):
        with column:
            opened = card(week_start + timedelta(days=offset)) or opened

    with st.expander("Weekend", icon=":material/weekend:"):
        for column, offset in zip(st.columns(2), (5, 6)):
            with column:
                opened = card(week_start + timedelta(days=offset)) or opened

    if rules:
        st.html("<style>" + "\n".join(rules) + "</style>")
    if opened is not None:
        _open(opened, steps, prefix,
              [NO_PROJECT] + list(db.projects()["name"]))
