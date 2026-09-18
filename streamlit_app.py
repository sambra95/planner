"""Planner - a personal task list, work diary and weekly review."""

from datetime import date, timedelta

import streamlit as st

import db

st.set_page_config(page_title="Planner", page_icon=":material/event_note:",
                   layout="wide")

page = st.navigation([
    st.Page("app_pages/tasks.py", title="Tasks", icon=":material/checklist:"),
    st.Page("app_pages/week.py", title="Week", icon=":material/calendar_view_week:"),
    st.Page("app_pages/review.py", title="Review", icon=":material/rate_review:"),
], position="top")

st.title("Planner", anchor=False)
if db.is_local():
    st.caption(":orange-badge[local database] Saving to planner.db in this folder. "
               "Set the `connections.planner` secret to use Postgres.")

# The end-of-week nudge: this week once Friday comes, last week before that.
today = date.today()
monday = today - timedelta(days=today.weekday())
due = monday if today.weekday() >= 4 else monday - timedelta(weeks=1)
if not any(db.review(due).values()):
    st.info(f"Your review for the week of {due:%d %b} is still empty.",
            icon=":material/rate_review:")

page.run()
