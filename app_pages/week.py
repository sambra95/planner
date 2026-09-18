"""The calendar, one week at a time: work times, focused hours, the day's task
checklist and a comment box, with the week's totals across the top.

Every widget saves as you change it, so there is nothing to submit.
"""

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

import db

#: Contracted hours in a working day. Overtime is measured against this.
STANDARD_DAY = 7.4

today = date.today()
if "week_start" not in st.session_state:
    st.session_state.week_start = today - timedelta(days=today.weekday())


def _shift(weeks: int) -> None:
    st.session_state.week_start += timedelta(weeks=weeks)


def _this_week() -> None:
    st.session_state.week_start = today - timedelta(days=today.weekday())


def _value(record: dict, field: str):
    """One field of a day's record, with missing values as None."""
    value = record.get(field)
    return None if value is None or pd.isna(value) else value


def _clock(value) -> time | None:
    return datetime.strptime(value, "%H:%M").time() if value else None


def _hours(start: time | None, end: time | None) -> float | None:
    """Hours between two clock times, or None when the day is not filled in."""
    if not (start and end):
        return None
    worked = datetime.combine(date.min, end) - datetime.combine(date.min, start)
    return max(0.0, worked.total_seconds() / 3600)


def _save_day(day: date) -> None:
    db.save_day(day, st.session_state[f"start:{day}"], st.session_state[f"end:{day}"],
                st.session_state[f"focus:{day}"], st.session_state[f"comment:{day}"])


def _toggle_task(task_id: int, day: date) -> None:
    db.set_task_done(task_id, day if st.session_state[f"task:{task_id}"] else None)


def _render_day(day: date, record: dict, tasks: pd.DataFrame) -> None:
    """One day's card: times, focus, checklist, comment."""
    with st.container(border=True):
        st.markdown(f"**{day:%a %-d %b}**"
                    + (" :blue-badge[today]" if day == today else ""))
        start = st.time_input("Start", _clock(_value(record, "start_time")), step=900,
                              key=f"start:{day}", on_change=_save_day, args=(day,))
        end = st.time_input("End", _clock(_value(record, "end_time")), step=900,
                            key=f"end:{day}", on_change=_save_day, args=(day,))
        st.number_input("Focused hours", min_value=0.0, max_value=24.0, step=0.5,
                        value=_value(record, "focus_hours"), key=f"focus:{day}",
                        on_change=_save_day, args=(day,))

        worked = _hours(start, end)
        st.caption(f"{round(worked, 2):g} h worked" if worked else "No hours yet")

        for task in tasks.itertuples():
            st.checkbox(task.title, value=not pd.isna(task.done_on),
                        key=f"task:{task.id}", on_change=_toggle_task,
                        args=(task.id, day))
        if tasks.empty:
            st.caption("No tasks assigned.")

        st.text_area("Comments", value=_value(record, "comment") or "", height=80,
                     key=f"comment:{day}", on_change=_save_day, args=(day,))


week_start = st.session_state.week_start
week_end = week_start + timedelta(days=6)

days = db.days_in(week_start, week_end)
records = {row["day"].date(): row for _, row in days.iterrows()}
tasks = db.tasks_in(week_start, week_end)

with st.container(horizontal=True, vertical_alignment="center"):
    st.button("Previous", icon=":material/chevron_left:", on_click=_shift, args=(-1,))
    st.button("Next", icon=":material/chevron_right:", on_click=_shift, args=(1,))
    st.button("This week", on_click=_this_week)
    st.markdown(f"**{week_start:%d %b} – {week_end:%d %b %Y}**")

worked = [_hours(_clock(_value(r, "start_time")), _clock(_value(r, "end_time")))
          for r in records.values()]
worked = [hours for hours in worked if hours]
focused = [_value(r, "focus_hours") for r in records.values()]
overtime = sum(worked) - STANDARD_DAY * len(worked)

totals = st.columns(3)
totals[0].metric("Hours worked", f"{sum(worked):.1f} h", border=True)
totals[1].metric("Focused hours", f"{sum(f for f in focused if f):.1f} h", border=True)
totals[2].metric("Overtime", f"{overtime:+.1f} h", border=True,
                 help=f"Against {STANDARD_DAY} h for each of the "
                      f"{len(worked)} day(s) with hours recorded.")

for column, offset in zip(st.columns(5), range(5)):
    day = week_start + timedelta(days=offset)
    with column:
        _render_day(day, records.get(day, {}), tasks[tasks["day"] == pd.Timestamp(day)])

with st.expander("Weekend", icon=":material/weekend:"):
    for column, offset in zip(st.columns(2), (5, 6)):
        day = week_start + timedelta(days=offset)
        with column:
            _render_day(day, records.get(day, {}),
                        tasks[tasks["day"] == pd.Timestamp(day)])
