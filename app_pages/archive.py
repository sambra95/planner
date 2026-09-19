"""Archive: the projects retired, then every week recorded, with the week
you pick opened up underneath."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

import daycard
import db
import weeksummary
from worktime import WEEK_HOURS, monday_of, totals, week_records

def _save_answer(week_start: date, question: str) -> None:
    """One answer, written as it is typed; the rest of the week is untouched."""
    db.save_review(week_start,
                   {question: st.session_state[f"archive:{week_start}:{question}"]})


days = db.all_days()
tasks = db.completed_tasks()
reviews = db.all_reviews()

if days.empty and tasks.empty and reviews.empty:
    st.caption("Nothing recorded yet.")
    st.stop()

# The Monday that starts each record's week, so everything groups the same way.
for frame, column in ((days, "day"), (tasks, "done_on"), (reviews, "week_start")):
    frame["week"] = frame[column].dt.to_period("W-SUN").dt.start_time

# This week is always offered, recorded or not, since it is what opens first.
this_week = pd.Timestamp(monday_of(date.today()))
weeks = sorted(set(days["week"]) | set(tasks["week"]) | set(reviews["week"])
               | {this_week}, reverse=True)

st.markdown("**Weeks**")


chosen = st.selectbox("Open a week", weeks, index=weeks.index(this_week),
                      format_func=lambda week: f"{week:%d %b %Y}")

start = chosen.date()
end = start + timedelta(days=6)
# `days` already holds every day, so the chosen week is a filter, not a query.
daycard.render_week(start, {row["day"].date(): row
                            for _, row in days[days["week"] == chosen].iterrows()},
                    db.items_in(start, end), db.milestones_in(start, end),
                    prefix="archive:")

st.divider()
st.markdown("**Review**")
# Laid out as the Review page lays it out: the week in figures beside what you
# made of it, and the answers still editable here.
summary, writing = st.columns(2, gap="large")

with summary:
    weeksummary.render(start)

with writing:
    saved_answers = db.review(start)
    for question in db.REVIEW_QUESTIONS:
        st.text_area(question, value=saved_answers.get(question, ""), height=150,
                     key=f"archive:{start}:{question}", on_change=_save_answer,
                     args=(start, question))

st.divider()
st.markdown("**Every week**")


def _summarise(week) -> dict:
    """One row a week, counted the way the week's own cards count it."""
    saved = {row["day"].date(): row
             for _, row in days[days["week"] == week].iterrows()}
    worked, breaks, overtime = totals(week_records(week.date(), saved))
    return {"Week beginning": week, "Hours worked": worked, "Break": breaks,
            "Overtime": overtime,
            "Tasks completed": int((tasks["week"] == week).sum()),
            "Reviewed": bool(reviews[reviews["week"] == week]["answer"].notna().any())}


st.dataframe(pd.DataFrame([_summarise(week) for week in weeks]),
             hide_index=True, width="stretch", column_config={
    "Week beginning": st.column_config.DateColumn(format="ddd DD MMM YYYY"),
    "Hours worked": st.column_config.NumberColumn(format="%.1f h"),
    "Break": st.column_config.NumberColumn(format="%.1f h"),
    "Overtime": st.column_config.NumberColumn(
        format="%+.1f h",
        help=f"Against a {WEEK_HOURS:g} h week, less any holiday."),
    "Reviewed": st.column_config.CheckboxColumn(),
})

st.divider()
st.markdown("**Archived projects**")

retired = db.projects()
retired = retired[retired["archived"] == 1]
if retired.empty:
    st.caption("None archived.")
for project in retired.itertuples():
    with st.container(border=True, key=f"retired-{project.id}"):
        row = st.columns([7, 2.4, 0.6], vertical_alignment="center")
        row[0].markdown(f"**{project.name}**")
        if not pd.isna(project.description):
            row[0].caption(project.description)
        span = " - ".join(f"{stamp:%d %b %Y}" for stamp in
                          (project.start_on, project.end_on) if not pd.isna(stamp))
        row[1].caption(span or "no dates")
        if row[2].button("", icon=":material/unarchive:",
                         key=f"retired_restore:{project.id}",
                         help="Put it back, with a colour of its own"):
            db.restore_project(project.id)
            st.rerun()

st.divider()
st.markdown("**Backups**")

outcome = st.session_state.pop("restored", None)
if outcome:
    st.success(outcome)

# One row: the button sizes to its label and the uploader takes the rest.
with st.container(horizontal=True, vertical_alignment="center"):
    st.download_button("Backup history", data=db.snapshot,
                       file_name=f"planner_backup_{date.today():%d%m%y}.db",
                       mime="application/vnd.sqlite3", icon=":material/download:",
                       help="Your whole history, as one file.")
    restoring = st.file_uploader("Restore history", type=["db"],
                                 label_visibility="collapsed",
                                 help="A file saved by Backup history.")

if restoring is not None:
    how = st.segmented_control("How to apply it", ["Merge", "Overwrite"],
                               default="Merge", label_visibility="collapsed")
    with st.popover(f"{how} this history", icon=":material/upload:"):
        if how == "Overwrite":
            st.markdown("**Replace everything with this file?**")
            st.caption("Every task, day, project and review in the app is written "
                       "over. This cannot be undone, so back up first.")
        else:
            st.markdown("**Add what is missing from this file?**")
            st.caption("Nothing here is changed or removed. A task, meeting or "
                       "paper of the same kind, title and day is already here, "
                       "so it is left alone.")
        if st.button("Yes, go ahead", type="primary"):
            try:
                if how == "Overwrite":
                    db.restore(restoring.getvalue())
                    outcome = "History replaced."
                else:
                    added = db.merge(restoring.getvalue())
                    outcome = ("Added " + ", ".join(f"{count} {name}"
                                                    for name, count in added.items())
                               if added else "Nothing to add: it is all here already.")
            except ValueError as problem:
                st.error(str(problem))
            else:
                # The message has to outlive the rerun that redraws the page.
                st.session_state["restored"] = outcome
                st.rerun()
