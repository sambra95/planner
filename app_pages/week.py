"""My Week: the calendar a week at a time, with its review underneath - the
same week, planned and then looked back on, and what it added up to counted
there. Every widget saves as you change it."""

from datetime import date, timedelta

import streamlit as st

import daycard
import db
import weeksummary
from palette import css_class, lightened
from worktime import monday_of

today = date.today()
st.session_state.setdefault("week_start", monday_of(today))


#: The picker's grid: seven weeks to a row, which is as narrow as a cell can be
#: and still carry the date beside the number.
WEEKS_ACROSS = 7

#: How wide the two week steps are, in pixels. An icon on its own leaves a
#: button about 40 of them wide, and these are worth hitting without aiming.
STEP_WIDTH = 200

#: The picker's label doubles as the page's heading, so it is sized like the
#: figures below it. Streamlit has no variable for that size to borrow.
LABEL_SIZE = "2.25rem"

#: The header and its two steps at one height, so the row reads as one control:
#: their own padding does not match.
ROW_HEIGHT = "3.5rem"

#: What Streamlit fills a plain button with, for the title between two of them.
BUTTON_FACE = lightened(st.get_option("theme.backgroundColor"))

PICKER = css_class("week-picker")
PICKER_CSS = f"""<style>
.{PICKER} summary {{
    font-size: {LABEL_SIZE};
    align-items: center;
    height: {ROW_HEIGHT};
    background-color: {BUTTON_FACE};
}}
/* The wrapper holding the label is the full width, so the text is centred
   inside it: centring the row itself has nothing to spare. */
.{PICKER} summary > span > div {{ justify-content: center; }}
/* Nothing but the week in the header, so the chevron goes. It is the icon in
   there with no test id of its own. Without :has() the rule is dropped and the
   chevron simply stays. */
.{PICKER} summary > span > span:has([data-testid="stIconMaterial"]) {{
    display: none;
}}
.{PICKER} summary p {{ font-size: {LABEL_SIZE}; }}
.{css_class("week_back")} button, .{css_class("week_on")} button {{
    height: {ROW_HEIGHT};
}}
</style>"""


def _shown(week_start: date) -> None:
    """Show `week_start`, and let the grid go back to following it."""
    st.session_state.week_start = week_start
    st.session_state.pop("grid_year", None)


def _shift(weeks: int) -> None:
    """The week before or after the one being shown."""
    _shown(st.session_state.week_start + timedelta(weeks=weeks))


def _step_year(by: int) -> None:
    """Look at another year's weeks without leaving the week being shown."""
    st.session_state.grid_year += by


def _year_grid(year: int, recorded: set, viewed: date) -> None:
    """Every week of `year` as a button, numbered and dated by the Monday it
    starts on. This week is filled in, a week with anything recorded in it is
    outlined, and an empty one is plain; the week being shown is the bold one.
    The 28th of December is always in the last week of its year, which is how a
    53-week year is told from a 52-week one."""
    last = date(year, 12, 28).isocalendar()[1]
    this_week = monday_of(today)
    for first in range(1, last + 1, WEEKS_ACROSS):
        row = st.columns(WEEKS_ACROSS)
        for column, number in zip(row, range(first, last + 1)):
            monday = date.fromisocalendar(year, number, 1)
            face = f"{number} · {monday:%d %b}"
            column.button(
                f"**{face}**" if monday == viewed else face,
                key=f"week_pick:{monday}", width="stretch",
                type=("primary" if monday == this_week
                      else "secondary" if monday in recorded else "tertiary"),
                on_click=_shown, args=(monday,))


def _save_answer(week_start: date, question: str) -> None:
    """One answer, written as it is typed; the rest of the week is untouched."""
    db.save_review(week_start,
                   {question: st.session_state[f"week:{week_start}:{question}"]})


week_start = st.session_state.week_start
week_end = week_start + timedelta(days=6)

days = db.days_in(week_start, week_end)
records = {row["day"].date(): row for _, row in days.iterrows()}
tasks = db.items_in(week_start, week_end)
milestones = db.milestones_in(week_start, week_end)

# Which weeks have anything in them, for the grid to mark. The grid follows the
# week being shown until the year buttons send it elsewhere.
recorded = set(db.recorded_weeks())
# Its ISO year, not its calendar one: the week beginning 29 December 2025 is
# the first week of 2026, and 2026's grid is the one holding it.
year = st.session_state.setdefault("grid_year", week_start.isocalendar()[0])

# The picker is its own title. An expander is known by its label, so one naming
# the week closes whenever that changes - which is just after one is picked. The
# steps either side go a week at a time, and sit at the top so they stay beside
# the label once the grid is open.
st.html(PICKER_CSS)
picker = st.container(horizontal=True, vertical_alignment="top",
                      key="week-picker")
picker.button("", icon=":material/chevron_left:", key="week_back",
              width=STEP_WIDTH, on_click=_shift, args=(-1,))
with picker.expander(f"{week_start:%d %b} – {week_end:%d %b %Y}"):
    # Packed in a row rather than laid out in columns, so the year sits between
    # the two arrows instead of at the left edge of a column of its own.
    with st.container(horizontal=True, vertical_alignment="center"):
        st.button("", icon=":material/chevron_left:", key="year_back",
                  on_click=_step_year, args=(-1,))
        st.markdown(f"**{year}**")
        st.button("", icon=":material/chevron_right:", key="year_on",
                  on_click=_step_year, args=(1,))
    _year_grid(year, recorded, week_start)
picker.button("", icon=":material/chevron_right:", key="week_on",
              width=STEP_WIDTH, on_click=_shift, args=(1,))

daycard.render_week(week_start, records, tasks, milestones, prefix="week:")

st.divider()
st.markdown("**Review**")
# The week in figures beside what you made of it, for whichever week the cards
# above are showing.
summary, writing = st.columns(2, gap="large")

with summary:
    weeksummary.render(week_start, records, tasks)

with writing:
    answers = db.review(week_start)
    for question in db.REVIEW_QUESTIONS:
        st.text_area(question, value=answers.get(question, ""), height=150,
                     key=f"week:{week_start}:{question}", on_change=_save_answer,
                     args=(week_start, question))
