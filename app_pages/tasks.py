"""Tasks: everything still to do. A task is finished only by its own checkbox;
ticking every step under it changes nothing."""

from datetime import date

import pandas as pd
import streamlit as st

import db
from palette import NO_PROJECT, card_css, strike

today = date.today()


def _add_task() -> None:
    db.add_task(st.session_state["new_task"])
    st.session_state["new_task"] = ""


def _rename(task_id: int) -> None:
    db.rename_task(task_id, st.session_state[f"title:{task_id}"])


def _set_description(task_id: int) -> None:
    db.set_task_description(task_id, st.session_state[f"about:{task_id}"])


def _set_day(task_id: int) -> None:
    db.set_task_day(task_id, st.session_state[f"day:{task_id}"])


def _set_project(task_id: int) -> None:
    chosen = st.session_state[f"project:{task_id}"]
    db.set_task_project(task_id, None if chosen == NO_PROJECT else chosen)


def _toggle_task(task_id: int) -> None:
    """Finishing here files it under today; a day's card uses that day."""
    db.set_task_done(task_id, today if st.session_state[f"done:{task_id}"] else None)


def _toggle_step(step_id: int) -> None:
    """A step stands alone: ticking it never finishes the task above it."""
    db.set_step_done(step_id, st.session_state[f"step:{step_id}"])


def _add_step(task_id: int) -> None:
    db.add_step(task_id, st.session_state[f"new_step:{task_id}"])
    st.session_state[f"new_step:{task_id}"] = ""


st.subheader("Open tasks", anchor=False)
st.caption("Give a task a day and it appears in that day's checklist. Anything "
           "still open stays on this list until you finish it. Steps are yours "
           "to tick as you go; only the task's own box finishes it. Meetings "
           "live on their own page.")

st.text_input("New task", key="new_task", placeholder="Add a task…",
              label_visibility="collapsed", on_change=_add_task)

tasks = db.open_tasks()
projects = db.projects()
steps_by_task = db.open_steps()
names = [NO_PROJECT] + list(projects["name"])
colours = dict(zip(projects["name"], projects["colour"]))
rules = []

if tasks.empty:
    st.caption("Nothing open.")

for task in tasks.itertuples():
    day = None if pd.isna(task.day) else task.day.date()
    if task.project in colours:
        rules.append(card_css(f"task-{task.id}", colours[task.project]))
    with st.container(border=True, key=f"task-{task.id}"):
        head = st.columns([0.4, 5, 2, 2, 0.5], vertical_alignment="center")
        head[0].checkbox("Done", value=False, key=f"done:{task.id}",
                         label_visibility="collapsed", on_change=_toggle_task,
                         args=(task.id,))
        head[1].text_input("Task", value=task.title, key=f"title:{task.id}",
                           label_visibility="collapsed", on_change=_rename,
                           args=(task.id,))
        head[2].selectbox("Project", names, key=f"project:{task.id}",
                          index=names.index(task.project) if task.project in names
                          else 0, label_visibility="collapsed",
                          on_change=_set_project, args=(task.id,))
        head[3].date_input("Day", value=day, key=f"day:{task.id}", format="DD/MM/YYYY",
                           label_visibility="collapsed", on_change=_set_day,
                           args=(task.id,))
        head[4].button("", icon=":material/delete:", key=f"drop:{task.id}",
                       on_click=db.delete_task, args=(task.id,))

        about = st.columns([0.6, 6, 3.4], vertical_alignment="center")
        about[1].text_input("Description", key=f"about:{task.id}",
                            value="" if pd.isna(task.description) else task.description,
                            placeholder="Add a description…",
                            label_visibility="collapsed",
                            on_change=_set_description, args=(task.id,))

        steps = steps_by_task[steps_by_task["task_id"] == task.id]
        for step in steps.itertuples():
            # The empty first column indents these as substeps.
            row = st.columns([0.6, 8.4, 0.5], vertical_alignment="center")
            row[1].checkbox(strike(step.title, bool(step.done)),
                            value=bool(step.done), key=f"step:{step.id}",
                            on_change=_toggle_step, args=(step.id,))
            row[2].button("", icon=":material/close:", key=f"drop_step:{step.id}",
                          on_click=db.delete_step, args=(step.id,))

        done = int(steps["done"].sum())
        hint = (f"Add a step… ({done}/{len(steps)} done)" if len(steps)
                else "Add a step…")
        adder = st.columns([0.6, 4, 5.4], vertical_alignment="center")
        adder[1].text_input("New step", key=f"new_step:{task.id}", placeholder=hint,
                            label_visibility="collapsed", on_change=_add_step,
                            args=(task.id,))

# One style block for every card that belongs to a project.
if rules:
    st.html("<style>" + "\n".join(rules) + "</style>")
