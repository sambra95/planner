"""The end-of-week questions. Pick any date to see or fill in that week."""

from datetime import date, timedelta

import streamlit as st

import db

#: The questions asked each week. Reword them freely; answers already saved keep
#: the wording they were asked under.
QUESTIONS = [
    "What went well?",
    "What did not go so well?",
    "What blocked me?",
    "What is my focus next week?",
]

today = date.today()
picked = st.date_input("Week of", value=today - timedelta(days=today.weekday()),
                       format="DD/MM/YYYY")
week_start = picked - timedelta(days=picked.weekday())
st.caption(f"Week of {week_start:%d %b} – {week_start + timedelta(days=6):%d %b %Y}")

answers = db.review(week_start)
with st.form("review"):
    responses = {question: st.text_area(question, value=answers.get(question, ""),
                                        height=90, key=f"{week_start}:{question}")
                 for question in QUESTIONS}
    if st.form_submit_button("Save review", icon=":material/save:", type="primary"):
        db.save_review(week_start, responses)
        st.toast("Review saved", icon=":material/check_circle:")
