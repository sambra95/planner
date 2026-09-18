"""The My Week tab: the calendar, one week at a time, with work times, breaks,
the day's checklist and a comment box, and the week's totals on top. It is the
first thing you see, so it is the week you are in.

Every widget saves as you change it, so there is nothing to submit.
"""

from datetime import date, timedelta

import streamlit as st

import daycard
import db
from worktime import WEEK_HOURS, expected, monday_of, totals, week_records

today = date.today()
st.session_state.setdefault("week_start", monday_of(today))


def _shift(weeks: int) -> None:
    st.session_state.week_start += timedelta(weeks=weeks)


def _this_week() -> None:
    st.session_state.week_start = monday_of(today)


week_start = st.session_state.week_start
week_end = week_start + timedelta(days=6)

days = db.days_in(week_start, week_end)
records = {row["day"].date(): row for _, row in days.iterrows()}
tasks = db.tasks_in(week_start, week_end)
steps = db.steps_in(week_start, week_end)

with st.container(horizontal=True, vertical_alignment="center"):
    st.button("Previous", icon=":material/chevron_left:", on_click=_shift, args=(-1,))
    st.button("Next", icon=":material/chevron_right:", on_click=_shift, args=(1,))
    st.button("This week", on_click=_this_week)
    st.markdown(f"**{week_start:%d %b} – {week_end:%d %b %Y}**")

# An unfilled weekday counts as the ordinary day its card is showing.
counted = week_records(week_start, records)
hours_worked, breaks, overtime = totals(counted)
owed = expected(counted)

metrics = st.columns(3)
metrics[0].metric("Hours worked", f"{hours_worked:.1f} h", border=True)
metrics[1].metric("Break", f"{breaks:.1f} h", border=True)
metrics[2].metric("Overtime", f"{overtime:+.1f} h", border=True,
                  help=f"Against the {owed:g} h this week owes"
                       + (f" ({WEEK_HOURS:g} h, less any holiday)."
                          if owed != WEEK_HOURS else "."))

daycard.render_week(week_start, records, tasks, steps, prefix="week:")
