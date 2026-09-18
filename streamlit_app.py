"""Planner - a personal task list, work diary and weekly review."""

from datetime import date, timedelta
from pathlib import Path

import streamlit as st

import db
from palette import INPUT_CSS, NAV_CSS, SECTION_CSS

#: Beside this file, not the working directory: the packaged app starts elsewhere.
ASSETS = Path(__file__).resolve().parent / "assets"

st.set_page_config(page_title="Planner", page_icon=str(ASSETS / "logo.png"),
                   layout="wide")
st.logo(str(ASSETS / "logo.svg"), size="large")

page = st.navigation([
    st.Page("app_pages/week.py", title="My Week",
            icon=":material/calendar_view_week:"),
    st.Page("app_pages/tasks.py", title="Tasks", icon=":material/checklist:"),
    st.Page("app_pages/meetings.py", title="Meetings", icon=":material/groups:"),
    st.Page("app_pages/papers.py", title="Papers", icon=":material/menu_book:"),
    st.Page("app_pages/review.py", title="Review", icon=":material/rate_review:"),
    st.Page("app_pages/projects.py", title="Projects", icon=":material/folder:"),
    st.Page("app_pages/archive.py", title="Archive", icon=":material/inventory_2:"),
], position="top")

# A task or meeting settles onto its own day once that day is over.
db.close_past_days()

st.html(SECTION_CSS)
st.html(INPUT_CSS)
st.html(NAV_CSS)

# The end-of-week nudge: this week once Friday comes, last week before that.
today = date.today()
monday = today - timedelta(days=today.weekday())
due = monday if today.weekday() >= 4 else monday - timedelta(weeks=1)
if not any(db.review(due).values()):
    st.info(f"Your review for the week of {due:%d %b} is still empty.",
            icon=":material/rate_review:")

page.run()
