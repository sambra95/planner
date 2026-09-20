"""My Week: the calendar a week at a time, with its review underneath - the
same week, planned and then looked back on, and what it added up to counted
there. Every widget saves as you change it."""

from datetime import date, timedelta

import streamlit as st

import daycard
import db
import weeksummary
from palette import lightened
from worktime import monday_of

today = date.today()
st.session_state.setdefault("week_start", monday_of(today))


#: The picker's grid: seven weeks to a row, which is as narrow as a cell can be
#: and still carry the date beside the number.
WEEKS_ACROSS = 7

#: How wide the two week steps are, in pixels. An icon on its own leaves a
#: button about 40 of them wide, and these are worth hitting without aiming.
STEP_WIDTH = 200

#: The picker's label is the page's heading now, so it is set at the size the
#: figures under it print their numbers at, rather than an expander's own body
#: text. Streamlit has no variable for it to borrow, so the size is written out.
LABEL_SIZE = "2.25rem"

#: The header and the two steps beside it, at one height so the row reads as a
#: single control. Both are set from here rather than left to their own padding,
#: which is the only way the three are sure to match.
ROW_HEIGHT = "3.5rem"

#: What a plain button is filled with, so the title beside two of them reads as
#: part of the same row rather than as a panel behind it.
BUTTON_FACE = lightened(st.get_option("theme.backgroundColor"))

PICKER_CSS = f"""<style>
.st-key-week-picker summary {{
    font-size: {LABEL_SIZE};
    align-items: center;
    height: {ROW_HEIGHT};
    background-color: {BUTTON_FACE};
}}
/* The header is a row of the chevron and then a wrapper holding the label,
   and that wrapper is the full width - so the text is centred inside it,
   rather than by centring the row, which has nothing to spare. */
.st-key-week-picker summary > span > div {{ justify-content: center; }}
/* Nothing but the week itself in the header, so the chevron goes too. It sits
   in a plain wrapping span, known by the material icon inside it. A browser
   without :has() drops the rule and simply keeps the chevron. */
.st-key-week-picker summary > span > span:has([data-testid="stIconMaterial"]) {{
    display: none;
}}
.st-key-week-picker summary p {{ font-size: {LABEL_SIZE}; }}
.st-key-week_back button, .st-key-week_on button {{ height: {ROW_HEIGHT}; }}
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
    st.session_state.grid_year = st.session_state.grid_year + by


def _year_grid(year: int, recorded: set, viewed: date) -> None:
    """Every week of `year` as a button, numbered and dated by the Monday it
    starts on. This week is filled in, a week with anything recorded in it is
    outlined, and an empty one is plain; the week being shown is the bold one.
    The 28th of December is always in the last week of its year, which is how a
    53-week year is told from a 52-week one."""
    last = date(year, 12, 28).isocalendar()[1]
    for first in range(1, last + 1, WEEKS_ACROSS):
        row = st.columns(WEEKS_ACROSS)
        for column, number in zip(row, range(first, first + WEEKS_ACROSS)):
            if number > last:
                break
            monday = date.fromisocalendar(year, number, 1)
            face = f"{number} · {monday:%d %b}"
            column.button(
                f"**{face}**" if monday == viewed else face,
                key=f"week_pick:{monday}", width="stretch",
                type=("primary" if monday == monday_of(today)
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

# Which weeks have anything in them, for the grid to mark. The grid is the way
# around the year, and follows the week being shown until the year buttons send
# it elsewhere.
recorded = set(db.recorded_weeks())
# Its ISO year, not its calendar one: the week beginning 29 December 2025 is
# the first week of 2026, and 2026's grid is the one holding it.
year = st.session_state.setdefault("grid_year", week_start.isocalendar()[0])

# The picker is its own title: the week it opens on is the week being shown. An
# expander is known by its label, so one that says which week it is closes each
# time that changes - which is when a week has just been picked. The steps to
# either side are a week at a time; the grid inside is for anywhere else, and
# they align to the top so they stay by the label when the grid is open.
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
# The week in figures beside what you made of it, and it follows whichever week
# the cards above are showing rather than always being this one.
summary, writing = st.columns(2, gap="large")

with summary:
    weeksummary.render(week_start)

with writing:
    answers = db.review(week_start)
    for question in db.REVIEW_QUESTIONS:
        st.text_area(question, value=answers.get(question, ""), height=150,
                     key=f"week:{week_start}:{question}", on_change=_save_answer,
                     args=(week_start, question))
