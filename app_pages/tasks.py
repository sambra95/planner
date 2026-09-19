"""Tasks: everything still to do. A task is finished only by its own checkbox;
ticking every milestone under it changes nothing. Each one opens the same editor a
day card uses, so a task reads the same wherever you meet it."""

from datetime import date

import pandas as pd
import streamlit as st

import daycard
import db
from palette import NO_PROJECT, chip_css, strike, style_block

today = date.today()


def _toggle_task(task_id: int) -> None:
    """Finishing here files it under today; a day's card uses that day."""
    db.set_task_done(task_id, today if st.session_state[f"done:{task_id}"] else None)


tasks = db.open_tasks()
milestones = db.open_milestones()
names = [NO_PROJECT] + list(db.projects()["name"])

daycard.add_button(db.TASK, names)

rules = []
opened = None

if tasks.empty:
    st.caption("Nothing open.")

for task in tasks.itertuples():
    own = milestones[milestones["task_id"] == task.id]
    tally = f" ({int(own['done'].sum())}/{len(own)})" if len(own) else ""
    day = "" if pd.isna(task.day) else f" · {task.day:%a %d %b}"
    if not pd.isna(task.colour):
        rules.append(chip_css(f"tasks:open:{task.id}", task.colour))

    line = st.columns([0.4, 9, 0.5], vertical_alignment="center")
    line[0].checkbox("Done", value=False, key=f"done:{task.id}",
                     label_visibility="collapsed", on_change=_toggle_task,
                     args=(task.id,))
    if line[1].button(f"{strike(task.title, False)}{tally}{day}",
                      key=f"tasks:open:{task.id}", width="stretch"):
        opened = task
    line[2].button("", icon=":material/delete:", key=f"drop:{task.id}",
                   on_click=db.delete_task, args=(task.id,))

# One style block for every chip, each in its project's colour.
if rules:
    st.html(style_block(rules))

if opened is not None:
    daycard.open_item(opened, "tasks:", names)
