"""Meetings: a month calendar, each on the day it happened - the day it was
held, or the day it is set for."""

import calendar
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
from palette import NO_PROJECT, badge, chip_css
from worktime import clock, when

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

#: Every day is drawn the same fixed height, so the grid reads as a calendar and
#: a busy month does not blow it up. A day needs EMPTY_DAY on its own and
#: PER_MEETING for each meeting on it, which is how many fit before the rest go
#: below the fold and the day is badged with its total instead.
CELL_HEIGHT = 120
EMPTY_DAY = 60
PER_MEETING = 48
VISIBLE = max(1, (CELL_HEIGHT - EMPTY_DAY) // PER_MEETING)


def _first_of_month(day: date) -> date:
    return day.replace(day=1)


def _shift(months: int) -> None:
    """Move the month in view, carrying over the year end in either direction."""
    start = st.session_state.month_start
    moved = start.month - 1 + months
    st.session_state.month_start = date(start.year + moved // 12, moved % 12 + 1, 1)


def _this_month() -> None:
    st.session_state.month_start = _first_of_month(date.today())


st.session_state.setdefault("month_start", _first_of_month(date.today()))

st.subheader("Meetings", anchor=False)
st.caption("Add a meeting and it appears on its day here and in that day's "
           "checklist in My Week. Click one to set its times or write it "
           "up under goals, comments and action points.")

with st.container(horizontal=True, vertical_alignment="center"):
    st.button("Previous", icon=":material/chevron_left:", on_click=_shift, args=(-1,))
    st.button("Next", icon=":material/chevron_right:", on_click=_shift, args=(1,))
    st.button("This month", on_click=_this_month)
    st.markdown(f"**{st.session_state.month_start:%B %Y}**")

month_start = st.session_state.month_start

# A new meeting lands on today when today is in view, otherwise on the 1st.
default_day = (date.today() if month_start.year == date.today().year
               and month_start.month == date.today().month else month_start)

with st.form("new_meeting", clear_on_submit=True, border=False):
    fields = st.columns([5, 2, 1], vertical_alignment="center")
    new_title = fields[0].text_input("Meeting", placeholder="Add a meeting…",
                                     label_visibility="collapsed")
    new_day = fields[1].date_input("Day", value=default_day, format="DD/MM/YYYY",
                                   label_visibility="collapsed")
    if fields[2].form_submit_button("Add", width="stretch"):
        db.add_meeting(new_title, new_day)
next_month = date(month_start.year + month_start.month // 12,
                  month_start.month % 12 + 1, 1)
month_end = next_month - timedelta(days=1)

# The grid spans whole weeks, so it runs into the months either side. Fetch those
# days too, then grey them out, rather than leaving holes at the corners.
grid = calendar.Calendar(firstweekday=0).monthdatescalendar(
    month_start.year, month_start.month)
meetings = db.meetings_in(grid[0][0], grid[-1][-1])
by_day = {day: frame for day, frame in meetings.groupby(meetings["on_day"].dt.date)}

def _rename(meeting_id: int) -> None:
    db.rename_task(meeting_id, st.session_state[f"open_title:{meeting_id}"])


def _set_day(meeting_id: int) -> None:
    """Move a meeting. A cleared box is ignored: it always has a day."""
    if chosen := st.session_state[f"open_day:{meeting_id}"]:
        db.move_meeting(meeting_id, chosen)


def _set_project(meeting_id: int) -> None:
    chosen = st.session_state[f"open_project:{meeting_id}"]
    db.set_task_project(meeting_id, None if chosen == NO_PROJECT else chosen)


#: The three sections a meeting is written up under.
SECTIONS = (("goals", "Goals"), ("notes", "Comments"), ("actions", "Action points"))


def _set_times(meeting_id: int) -> None:
    db.set_meeting_times(meeting_id,
                         st.session_state[f"open_start:{meeting_id}"],
                         st.session_state[f"open_end:{meeting_id}"])


def _save_section(meeting_id: int, field: str) -> None:
    db.set_task_note(meeting_id, field,
                     st.session_state[f"open_{field}:{meeting_id}"])


@st.dialog("Meeting", width="large", on_dismiss="rerun")
def _open(meeting, names: list[str]) -> None:
    """The meeting, opened from the calendar. A dialog is a fragment, so editing
    leaves it open; closing reruns the page so the calendar catches up."""
    st.caption(f"{meeting.on_day:%A %d %B %Y}"
               + ("" if pd.isna(meeting.done_on) else " · held"))

    st.text_input("Meeting", value=meeting.title, key=f"open_title:{meeting.id}",
                  on_change=_rename, args=(meeting.id,))

    side = st.columns(2)
    side[0].date_input("Day", value=meeting.on_day.date(),
                       key=f"open_day:{meeting.id}", format="DD/MM/YYYY",
                       on_change=_set_day, args=(meeting.id,))
    side[1].selectbox("Project", names, key=f"open_project:{meeting.id}",
                      index=names.index(meeting.project)
                      if meeting.project in names else 0,
                      on_change=_set_project, args=(meeting.id,))

    times = st.columns(2)
    times[0].time_input("From", clock(meeting.start_time), step=900,
                        key=f"open_start:{meeting.id}", on_change=_set_times,
                        args=(meeting.id,))
    times[1].time_input("To", clock(meeting.end_time), step=900,
                        key=f"open_end:{meeting.id}", on_change=_set_times,
                        args=(meeting.id,))

    for field, label in SECTIONS:
        st.text_area(label, height=140, key=f"open_{field}:{meeting.id}",
                     value="" if pd.isna(getattr(meeting, field))
                     else getattr(meeting, field),
                     placeholder=f"{label}…", on_change=_save_section,
                     args=(meeting.id, field))
    st.caption("Saved as you type.")

    with st.popover("Delete this meeting", icon=":material/delete:"):
        st.markdown("**Delete this meeting?**")
        st.caption("Its write-up goes with it. This cannot be undone.")
        if st.button("Yes, delete it", key=f"drop_meeting:{meeting.id}",
                     type="primary"):
            db.delete_task(meeting.id)
            # Rerunning the whole app, not just this fragment, closes the dialog
            # and redraws the calendar without the meeting.
            st.rerun(scope="app")


today = date.today()
rules = []
opened = None

for column, name in zip(st.columns(7), WEEKDAYS):
    column.caption(f"**{name}**")

for week in grid:
    for column, day in zip(st.columns(7), week):
        on_day = by_day.get(day, pd.DataFrame())
        # Anything past the fold is only reachable by scrolling the cell, so say
        # how many there are next to the date rather than leave them unannounced.
        tally = f" :gray-badge[{len(on_day)}]" if len(on_day) > VISIBLE else ""
        with column, st.container(border=True, height=CELL_HEIGHT):
            if day == today:
                st.markdown(f"**{day.day}** :blue-badge[today]{tally}")
            elif day.month == month_start.month:
                st.markdown(f"**{day.day}**{tally}")
            else:
                st.caption(f"{day.day}")
            for meeting in on_day.itertuples():
                # Buttons cannot render a colour directive in their label, so the
                # button itself is painted in the project's colour instead.
                if not pd.isna(meeting.colour):
                    rules.append(chip_css(f"open-{meeting.id}", meeting.colour))
                clock_face = when(meeting._asdict())
                if st.button(f"{clock_face} {meeting.title}".strip(),
                             key=f"open-{meeting.id}", width="stretch"):
                    opened = meeting

# The grid runs into the neighbouring months, so count only this one's days.
in_month = meetings[(meetings["on_day"] >= pd.Timestamp(month_start))
                    & (meetings["on_day"] <= pd.Timestamp(month_end))]
if in_month.empty:
    st.caption("No meetings this month.")

if rules:
    st.html("<style>" + "\n".join(rules) + "</style>")

if opened is not None:
    _open(opened, [NO_PROJECT] + list(db.projects()["name"]))
