"""Archive: every week you have recorded, summarised, with the week you pick
opened up underneath - its days exactly as the week view draws them, and the
review you wrote for it."""

from datetime import timedelta

import pandas as pd
import streamlit as st

import daycard
import db
from palette import badge
from worktime import WEEK_HOURS, totals, week_records

def _save_comments(paper_id: int) -> None:
    db.set_task_note(paper_id, "notes",
                     st.session_state[f"paper_notes:{paper_id}"])


@st.dialog("Paper", width="large")
def _open_paper(paper) -> None:
    """One read paper: what it was, and what you made of it."""
    st.caption(f"Read {paper.done_on:%A %d %B %Y}")
    st.markdown(f"### {paper.title}")
    if not pd.isna(paper.project):
        st.markdown(badge(paper.project, paper.colour))
    st.text_area("Comments", key=f"paper_notes:{paper.id}", height=240,
                 value="" if pd.isna(paper.notes) else paper.notes,
                 placeholder="Comments…", on_change=_save_comments,
                 args=(paper.id,))
    st.caption("Saved as you type.")


st.subheader("Archive", anchor=False)

days = db.all_days()
tasks = db.completed_tasks()
reviews = db.all_reviews()

if days.empty and tasks.empty and reviews.empty:
    st.caption("Nothing recorded yet.")
    st.stop()

# The Monday that starts each record's week, so everything groups the same way.
for frame, column in ((days, "day"), (tasks, "done_on"), (reviews, "week_start")):
    frame["week"] = frame[column].dt.to_period("W-SUN").dt.start_time

weeks = sorted(set(days["week"]) | set(tasks["week"]) | set(reviews["week"]),
               reverse=True)

st.markdown("**Papers read**")
query = st.text_input("Search papers", key="paper_search",
                      placeholder="Search titles, comments and projects…",
                      label_visibility="collapsed")
read = db.papers_read(query)

if read.empty:
    st.caption("No papers match." if query else "No papers read yet.")
else:
    # A table stays one height however long the list gets; the comments, which
    # are as long as they are, open on the row you pick.
    listing = pd.DataFrame({"Read": read["done_on"], "Paper": read["title"],
                            "Project": read["project"].fillna("—"),
                            "Comments": read["notes"].fillna("")})
    picked = st.dataframe(
        listing, hide_index=True, width="stretch", height=280,
        on_select="rerun", selection_mode="single-row",
        column_config={
            "Read": st.column_config.DateColumn(format="ddd DD MMM YYYY"),
            "Paper": st.column_config.TextColumn(width="large"),
            "Comments": st.column_config.TextColumn(width="medium"),
        })
    st.caption(f"{len(read)} paper(s)" + (" matching" if query else " read")
               + " · pick one to read or edit your comments")
    if picked.selection.rows:
        # One row, as a namedtuple: a dialog is a fragment and is handed its
        # arguments back on every rerun, and a Series does not survive that.
        chosen = read.iloc[[picked.selection.rows[0]]]
        _open_paper(next(chosen.itertuples()))

st.markdown("**Weeks**")


def _summarise(week) -> dict:
    saved = {row["day"].date(): row
             for _, row in days[days["week"] == week].iterrows()}
    worked, breaks, overtime = totals(week_records(week.date(), saved))
    return {"Week beginning": week, "Hours worked": worked, "Break": breaks,
            "Overtime": overtime, "Tasks done": int((tasks["week"] == week).sum()),
            "Reviewed": bool(reviews[reviews["week"] == week]["answer"].notna().any())}


summary = pd.DataFrame([_summarise(week) for week in weeks])

st.dataframe(summary, hide_index=True, width="stretch", column_config={
    "Week beginning": st.column_config.DateColumn(format="ddd DD MMM YYYY"),
    "Hours worked": st.column_config.NumberColumn(format="%.1f h"),
    "Break": st.column_config.NumberColumn(format="%.1f h"),
    "Overtime": st.column_config.NumberColumn(
        format="%+.1f h",
        help=f"Against a {WEEK_HOURS:g} h week, less any holiday."),
    "Reviewed": st.column_config.CheckboxColumn(),
})

chosen = st.selectbox("Open a week", weeks,
                      format_func=lambda week: f"{week:%d %b %Y}")

start = chosen.date()
end = start + timedelta(days=6)
st.caption("Untick a task to put it back on the open list.")
daycard.render_week(start, {row["day"].date(): row
                            for _, row in db.days_in(start, end).iterrows()},
                    db.tasks_in(start, end), db.steps_in(start, end),
                    prefix="archive:")

st.markdown("**Review**")
answers = reviews[reviews["week"] == chosen]
if answers.empty:
    st.caption("No review saved for this week.")
for answer in answers.itertuples():
    st.markdown(f"**{answer.question}**")
    st.write(answer.answer or "—")
