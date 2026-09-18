"""The end-of-week questions, for this week. Older weeks live in the
archive, where the same figures and boxes are shown."""

from datetime import date, timedelta

import streamlit as st

import db
import weeksummary
from worktime import monday_of


def _save_answer(week_start: date, question: str) -> None:
    """One answer, written as it is typed; the rest of the week is untouched."""
    db.save_review(week_start, {question: st.session_state[f"{week_start}:{question}"]})


#: Always this week. Any other week is read and edited in the archive.
week_start = monday_of(date.today())
st.caption(f"Week of {week_start:%d %b} – {week_start + timedelta(days=6):%d %b %Y}")

#: The week in figures on the left, what you made of it on the right.
summary, writing = st.columns(2, gap="large")

with summary:
    weeksummary.render(week_start)

with writing:
    answers = db.review(week_start)
    for question in db.REVIEW_QUESTIONS:
        st.text_area(question, value=answers.get(question, ""), height=150,
                     key=f"{week_start}:{question}", on_change=_save_answer,
                     args=(week_start, question))
