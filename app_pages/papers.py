"""Papers to read. A paper has no steps, just comments; tick it off and it
counts as read and keeps its comments in the archive."""

from datetime import date

import pandas as pd
import streamlit as st

import db
from palette import NO_PROJECT, card_css, style_block


def _rename(paper_id: int) -> None:
    db.rename_task(paper_id, st.session_state[f"paper_title:{paper_id}"])


def _set_day(paper_id: int) -> None:
    db.set_task_day(paper_id, st.session_state[f"paper_day:{paper_id}"])


def _set_project(paper_id: int) -> None:
    chosen = st.session_state[f"paper_project:{paper_id}"]
    db.set_task_project(paper_id, None if chosen == NO_PROJECT else chosen)


def _set_notes(paper_id: int) -> None:
    db.set_task_note(paper_id, "notes",
                     st.session_state[f"paper_notes:{paper_id}"])


def _mark_read(paper_id: int) -> None:
    """Read here records it as read today; a day's checklist uses that day."""
    db.set_task_done(paper_id, date.today() if
                     st.session_state[f"paper_read:{paper_id}"] else None)


with st.form("new_paper", clear_on_submit=True, border=False):
    fields = st.columns([8, 1], vertical_alignment="center")
    new_paper = fields[0].text_input("Paper", placeholder="Add a paper…",
                                     label_visibility="collapsed")
    if fields[1].form_submit_button("Add", width="stretch"):
        db.add_paper(new_paper)

papers = db.unread_papers()
names = [NO_PROJECT] + list(db.projects()["name"])
rules = []

if papers.empty:
    st.caption("Nothing to read.")

for paper in papers.itertuples():
    if not pd.isna(paper.colour):
        rules.append(card_css(f"paper-{paper.id}", paper.colour))
    with st.container(border=True, key=f"paper-{paper.id}"):
        head = st.columns([0.4, 5, 2, 2, 0.5], vertical_alignment="center")
        head[0].checkbox("Read", value=False, key=f"paper_read:{paper.id}",
                         label_visibility="collapsed", help="Mark as read",
                         on_change=_mark_read, args=(paper.id,))
        head[1].text_input("Paper", value=paper.title,
                           key=f"paper_title:{paper.id}",
                           label_visibility="collapsed", on_change=_rename,
                           args=(paper.id,))
        head[2].selectbox("Project", names, key=f"paper_project:{paper.id}",
                          index=names.index(paper.project)
                          if paper.project in names else 0,
                          label_visibility="collapsed", on_change=_set_project,
                          args=(paper.id,))
        head[3].date_input("Day", value=None if pd.isna(paper.day)
                           else paper.day.date(), key=f"paper_day:{paper.id}",
                           format="DD/MM/YYYY", label_visibility="collapsed",
                           on_change=_set_day, args=(paper.id,))
        head[4].button("", icon=":material/delete:", key=f"paper_drop:{paper.id}",
                       on_click=db.delete_task, args=(paper.id,))

        comments = st.columns([0.6, 8.9])
        comments[1].text_area("Comments", key=f"paper_notes:{paper.id}", height=110,
                              value="" if pd.isna(paper.notes) else paper.notes,
                              placeholder="Comments…", label_visibility="collapsed",
                              on_change=_set_notes, args=(paper.id,))

if rules:
    st.html(style_block(rules))
