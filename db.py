"""Every read and write the planner makes: one SQLite file and the helpers the
pages call. Dates go in as ISO strings and come back as pandas datetimes."""

from __future__ import annotations

import os
from datetime import date, time
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import inspect, text

from palette import ARCHIVED_COLOUR, as_hex, next_colour

def _local_database() -> str:
    """Where the SQLite file lives. The packaged app sets PLANNER_DB to point
    outside the bundle; a checkout keeps it beside this file. Absolute either
    way, since an app launched from the Dock starts in "/"."""
    override = os.environ.get("PLANNER_DB", "").strip()
    if override:
        path = Path(override).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path}"
    return f"sqlite:///{Path(__file__).resolve().parent / 'planner.db'}"


LOCAL_URL = _local_database()

_DATE_COLUMNS = ("day", "done_on", "on_day", "created_on", "week_start")

#: What a row in `tasks` is. They share a table, and differ in what hangs off
#: them: steps for a task, notes for the other two.
TASK = "task"
MEETING = "meeting"
PAPER = "paper"

#: Renamed columns: old name to new.
_RENAMED_COLUMNS = {"days": {"focus_hours": "unfocused_hours",
                             "unfocused_hours": "break_hours"},
                    "tasks": {"minutes": "notes"}}

#: Columns added per table, applied on connect. Fixed here in the source, never
#: taken from user input.
_ADDED_COLUMNS = {
    "tasks": {"project_id": "INTEGER", "description": "TEXT",
              "kind": "TEXT NOT NULL DEFAULT 'task'", "notes": "TEXT",
              "goals": "TEXT", "actions": "TEXT",
              "start_time": "TEXT", "end_time": "TEXT"},
    "days": {"holiday": "INTEGER NOT NULL DEFAULT 0"},
    "projects": {"archived": "INTEGER NOT NULL DEFAULT 0"},
}

#: Six queries join a row to its project; they share the wording.
_FROM_TASKS = " FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "

#: Step totals for a task, as two columns, in one statement.
_STEP_COUNTS = ("(SELECT COUNT(*) FROM steps s WHERE s.task_id = t.id) AS steps, "
                "(SELECT COUNT(*) FROM steps s WHERE s.task_id = t.id AND s.done = 1) "
                "AS steps_done")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    colour      TEXT NOT NULL,
    archived    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tasks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    day        DATE,
    done_on    DATE,
    created_on  DATE NOT NULL,
    project_id  INTEGER,
    description TEXT,
    kind        TEXT NOT NULL DEFAULT 'task',
    goals       TEXT,
    notes       TEXT,
    actions     TEXT,
    start_time  TEXT,
    end_time    TEXT
);
CREATE TABLE IF NOT EXISTS steps (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    title   TEXT NOT NULL,
    done    INTEGER NOT NULL DEFAULT 0
);
-- Every task query counts its steps with a correlated subquery. Without this,
-- each one scans the whole table. No semicolons in here: _create_tables splits
-- the schema on them.
CREATE INDEX IF NOT EXISTS steps_by_task ON steps(task_id);
CREATE TABLE IF NOT EXISTS days (
    day         DATE PRIMARY KEY,
    start_time  TEXT,
    end_time    TEXT,
    break_hours REAL,
    comment     TEXT,
    holiday     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS reviews (
    week_start DATE NOT NULL,
    question   TEXT NOT NULL,
    answer     TEXT,
    PRIMARY KEY (week_start, question)
);
"""


@st.cache_resource(show_spinner=False)
def _create_tables(_connection) -> None:
    """Create anything missing, once per session. The argument is underscored so
    Streamlit caches on the call rather than trying to hash the connection."""
    with _connection.session as session:
        for statement in _SCHEMA.strip().split(";"):
            if statement.strip():
                session.execute(text(statement))
        session.commit()
    _catch_up(_connection)


def _catch_up(connection) -> None:
    """Bring an older database up to the current schema. Renames run before
    additions so a renamed column is not re-added empty. Idempotent."""
    def columns(table: str) -> set[str]:
        return {column["name"]
                for column in inspect(connection.engine).get_columns(table)}

    for table, renames in _RENAMED_COLUMNS.items():
        for old_name, new_name in renames.items():
            present = columns(table)
            if old_name in present and new_name not in present:
                with connection.session as session:
                    session.execute(text(f"ALTER TABLE {table} RENAME COLUMN "
                                         f"{old_name} TO {new_name}"))
                    session.commit()

    for table, wanted in _ADDED_COLUMNS.items():
        present = columns(table)
        missing = [(name, kind) for name, kind in wanted.items()
                   if name not in present]
        if missing:
            with connection.session as session:
                for name, kind in missing:
                    session.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))
                session.commit()

    if "is_meeting" in columns("tasks"):
        with connection.session as session:
            session.execute(text("UPDATE tasks SET kind = :meeting "
                                 "WHERE is_meeting = 1 AND kind = :task"),
                            {"meeting": MEETING, "task": TASK})
            session.execute(text("ALTER TABLE tasks DROP COLUMN is_meeting"))
            session.commit()

    _unique_colours(connection)


def _unique_colours(connection) -> None:
    """Give every live project a hex colour of its own, oldest keeping it on a
    tie. Archived projects are skipped: they share one grey."""
    with connection.session as session:
        rows = session.execute(
            text("SELECT id, colour FROM projects WHERE archived = 0 "
                 "ORDER BY id")).all()
        used: list[str] = []
        for project_id, colour in rows:
            wanted = as_hex(colour)
            if wanted in used:
                wanted = next_colour(used)
            used.append(wanted)
            if wanted != colour:
                session.execute(
                    text("UPDATE projects SET colour = :colour WHERE id = :id"),
                    {"id": project_id, "colour": wanted})
        session.commit()


def _conn():
    """The connection (``st.connection`` caches it), with its tables in place."""
    conn = st.connection("planner", type="sql", url=LOCAL_URL)
    _create_tables(conn)
    return conn


def _read(sql: str, **params) -> pd.DataFrame:
    """A query straight to the database - never cached, so an edit shows at once."""
    with _conn().session as session:
        frame = pd.read_sql(text(sql), session.connection(), params=params)
    for column in frame.columns.intersection(_DATE_COLUMNS):
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def _write(sql: str, **params) -> None:
    with _conn().session as session:
        session.execute(text(sql), params)
        session.commit()


# --- Tasks ------------------------------------------------------------------

def open_tasks() -> pd.DataFrame:
    """Every task still to do, newest first. Meetings and papers live on their
    own pages and are not here."""
    frame = _read("SELECT t.id, t.title, t.day, t.description, "
                  "p.name AS project, "
                  + _STEP_COUNTS + _FROM_TASKS
                  + "WHERE t.done_on IS NULL AND t.kind = :kind "
                    "ORDER BY t.id DESC", kind=TASK)
    return frame


def add_task(title: str) -> None:
    """Create an open task with nothing else set yet."""
    if title := title.strip():
        _write("INSERT INTO tasks (title, created_on) VALUES (:title, :created_on)",
               title=title, created_on=date.today().isoformat())


def rename_task(task_id: int, title: str) -> None:
    if title := title.strip():
        _write("UPDATE tasks SET title = :title WHERE id = :id",
               id=task_id, title=title)


def set_task_description(task_id: int, description: str) -> None:
    """Set or clear a task's description. Blank means none."""
    _write("UPDATE tasks SET description = :description WHERE id = :id",
           id=task_id, description=description.strip() or None)


def set_task_day(task_id: int, day: date | None) -> None:
    _write("UPDATE tasks SET day = :day WHERE id = :id",
           id=task_id, day=day.isoformat() if day else None)


def set_task_project(task_id: int, project: str | None) -> None:
    _write("UPDATE tasks SET project_id = "
           "(SELECT id FROM projects WHERE name = :project) WHERE id = :id",
           id=task_id, project=project)


def _add_dated(title: str, day: date | None, kind: str) -> None:
    """Create a meeting or a paper: a titled thing of its kind, on a day or not
    yet on one."""
    if title := title.strip():
        _write("INSERT INTO tasks (title, day, created_on, kind) "
               "VALUES (:title, :day, :created_on, :kind)",
               title=title, day=day.isoformat() if day else None, kind=kind,
               created_on=date.today().isoformat())


#: Everything a dated row needs, for its card and for its editor.
_DATED_COLUMNS = ("SELECT t.id, t.title, t.goals, t.notes, t.actions, "
                  "t.start_time, t.end_time, t.done_on, t.description, "
                  "COALESCE(t.done_on, t.day) AS on_day, p.name AS project, "
                  "p.colour AS colour")


def _of_kind(kind: str, first: date, last: date) -> pd.DataFrame:
    """One kind filed against a day in the range, earliest first: under the day
    it was finished, or the day it is set for. Undated ones are not here."""
    return _read(_DATED_COLUMNS
                 + _FROM_TASKS
                 + "WHERE t.kind = :kind "
                 "AND COALESCE(t.done_on, t.day) BETWEEN :first AND :last "
                 "ORDER BY COALESCE(t.done_on, t.day), t.id",
                 kind=kind, first=first.isoformat(), last=last.isoformat())


def add_paper(title: str) -> None:
    """Add a paper to read. It starts with no day: give it one when you decide
    when to read it, and it joins that day's checklist then."""
    _add_dated(title, None, PAPER)


def unread_papers() -> pd.DataFrame:
    """Papers still to read, most recently added first."""
    return _read("SELECT t.id, t.title, t.day, t.notes, p.name AS project, "
                 "p.colour AS colour"
                 + _FROM_TASKS
                 + "WHERE t.done_on IS NULL AND t.kind = :kind "
                   "ORDER BY t.id DESC", kind=PAPER)


def papers_read(query: str = "") -> pd.DataFrame:
    """Papers read, newest first, narrowed to those whose title, comments or
    project contain `query`. Matched in the database; LOWER on both sides makes
    it case-insensitive."""
    return _read("SELECT t.id, t.title, t.notes, t.done_on, p.name AS project, "
                 "p.colour AS colour"
                 + _FROM_TASKS
                 + "WHERE t.kind = :kind AND t.done_on IS NOT NULL "
                 "AND (LOWER(t.title) LIKE :like "
                 "OR LOWER(COALESCE(t.notes, '')) LIKE :like "
                 "OR LOWER(COALESCE(p.name, '')) LIKE :like) "
                 "ORDER BY t.done_on DESC, t.id DESC",
                 kind=PAPER, like=f"%{query.strip().lower()}%")


def meetings_matching(query: str) -> pd.DataFrame:
    """Meetings whose title, write-up or project contain `query`, newest first.
    Matched in the database; LOWER on both sides makes it case-insensitive."""
    return _read(_DATED_COLUMNS
                 + _FROM_TASKS
                 + "WHERE t.kind = :kind AND ("
                 "LOWER(t.title) LIKE :like "
                 "OR LOWER(COALESCE(t.goals, '')) LIKE :like "
                 "OR LOWER(COALESCE(t.notes, '')) LIKE :like "
                 "OR LOWER(COALESCE(t.actions, '')) LIKE :like "
                 "OR LOWER(COALESCE(p.name, '')) LIKE :like) "
                 "ORDER BY COALESCE(t.done_on, t.day) DESC, t.id DESC",
                 kind=MEETING, like=f"%{query.strip().lower()}%")


def move_meeting(meeting_id: int, day: date) -> None:
    """Move a meeting, carrying its done_on: filing is by COALESCE(done_on,
    day), so leaving it behind would pin the meeting to its old day. A day gone
    by counts as held, a day to come does not."""
    _write("UPDATE tasks SET day = :day, done_on = :done_on "
           "WHERE id = :id AND kind = :kind",
           id=meeting_id, kind=MEETING, day=day.isoformat(),
           done_on=day.isoformat() if day < date.today() else None)


def add_meeting(title: str, day: date) -> None:
    """Create a meeting on a day. Kept off the open task list; made on the
    Meetings page."""
    if title := title.strip():
        _add_dated(title, day, MEETING)


#: The written sections. A meeting uses all three, a paper only comments. Named
#: here so `set_task_note` never takes a column name from user input.
NOTE_FIELDS = ("goals", "notes", "actions")


def set_meeting_times(task_id: int, start: time | None,
                      end: time | None) -> None:
    """When a meeting runs from and to. Both are optional: plenty of meetings
    are just a day in the diary."""
    _write("UPDATE tasks SET start_time = :start, end_time = :end WHERE id = :id",
           id=task_id, start=start.strftime("%H:%M") if start else None,
           end=end.strftime("%H:%M") if end else None)


def set_task_note(task_id: int, field: str, text: str) -> None:
    """Set one written section of a meeting or paper. Blank means none."""
    if field not in NOTE_FIELDS:
        raise ValueError(f"not a note field: {field!r}")
    _write(f"UPDATE tasks SET {field} = :text WHERE id = :id",
           id=task_id, text=text.strip() or None)


def close_past_days() -> None:
    """Settle every task and meeting whose day is over onto that day. Papers are
    left alone: an unread paper is not read just because its day has gone.
    Idempotent, so it can run on every rerun."""
    _write("UPDATE tasks SET done_on = day WHERE kind IN (:task, :meeting) "
           "AND done_on IS NULL AND day IS NOT NULL AND day < :today",
           task=TASK, meeting=MEETING, today=date.today().isoformat())


def meetings_in(first: date, last: date) -> pd.DataFrame:
    """Meetings filed against a day in the range, earliest first.

    Filed the same way tasks are: under the day it was finished once it is done,
    otherwise the day it is set for. A meeting with no day yet is not here.
    """
    return _of_kind(MEETING, first, last)


def delete_task(task_id: int) -> None:
    """Remove a task and the steps under it."""
    with _conn().session as session:
        session.execute(text("DELETE FROM steps WHERE task_id = :id"), {"id": task_id})
        session.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task_id})
        session.commit()


# --- Projects ---------------------------------------------------------------

def projects() -> pd.DataFrame:
    """Every project, live ones first. Archived ones stay so anything assigned
    to them still shows a name; they are grey and sorted last."""
    return _read("SELECT id, name, description, colour, archived FROM projects "
                 "ORDER BY archived, id")


def archive_project(project_id: int) -> None:
    """Retire a project, freeing its colour. Its tasks and papers keep it and
    turn grey with it."""
    _write("UPDATE projects SET archived = 1, colour = :grey WHERE id = :id",
           id=project_id, grey=ARCHIVED_COLOUR)


def restore_project(project_id: int) -> None:
    """Bring a project back, on whatever colour is free now."""
    with _conn().session as session:
        used = [row[0] for row in session.execute(
            text("SELECT colour FROM projects WHERE archived = 0"))]
        session.execute(
            text("UPDATE projects SET archived = 0, colour = :colour "
                 "WHERE id = :id"),
            {"id": project_id, "colour": next_colour(used)})
        session.commit()


def add_project(name: str) -> None:
    """Create a project, giving it the next colour no other project holds."""
    if name := name.strip():
        with _conn().session as session:
            used = [row[0] for row in
                    session.execute(text("SELECT colour FROM projects"))]
            session.execute(
                text("INSERT INTO projects (name, description, colour) "
                     "VALUES (:name, NULL, :colour)"),
                {"name": name, "colour": next_colour(used)})
            session.commit()


def rename_project(project_id: int, name: str) -> None:
    if name := name.strip():
        _write("UPDATE projects SET name = :name WHERE id = :id",
               id=project_id, name=name)


def set_project_description(project_id: int, description: str) -> None:
    """Set or clear a project's description. Blank means none."""
    _write("UPDATE projects SET description = :description WHERE id = :id",
           id=project_id, description=description.strip() or None)


def delete_project(project_id: int) -> None:
    """Remove a project. Its tasks are released, not deleted: they keep their
    history and simply show as having no project."""
    with _conn().session as session:
        session.execute(text("UPDATE tasks SET project_id = NULL "
                             "WHERE project_id = :id"), {"id": project_id})
        session.execute(text("DELETE FROM projects WHERE id = :id"),
                        {"id": project_id})
        session.commit()


# --- Tasks by day -----------------------------------------------------------

def tasks_in(first: date, last: date) -> pd.DataFrame:
    """Tasks filed against each day in the range, as `on_day`: a finished one
    under the day it was done, an open one under the day it is set for."""
    return _read("SELECT t.id, t.title, t.day, t.done_on, t.kind, t.description, "
                 "t.goals, t.notes, t.actions, t.start_time, t.end_time, "
                 "COALESCE(t.done_on, t.day) AS on_day, "
                 "p.name AS project, p.colour AS colour, "
                 + _STEP_COUNTS
                 + _FROM_TASKS
                 + "WHERE COALESCE(t.done_on, t.day) BETWEEN :first AND :last "
                 "ORDER BY t.id",
                 first=first.isoformat(), last=last.isoformat())


def set_task_done(task_id: int, day: date | None) -> None:
    """Tick a task off on `day`, or untick it when `day` is None."""
    _write("UPDATE tasks SET done_on = :done_on WHERE id = :id",
           id=task_id, done_on=day.isoformat() if day else None)


# --- Steps ------------------------------------------------------------------

def open_steps() -> pd.DataFrame:
    """Every step of every open task, in one query; the task list groups them.
    Asking per task would be a round trip each, on every rerun."""
    frame = _read("SELECT s.id, s.task_id, s.title, s.done FROM steps s "
                  "JOIN tasks t ON t.id = s.task_id "
                  "WHERE t.done_on IS NULL AND t.kind = :kind "
                  "ORDER BY s.task_id, s.id", kind=TASK)
    frame["done"] = frame["done"].astype(bool)
    return frame


def steps_in(first: date, last: date) -> pd.DataFrame:
    """Every step of every task filed against a day in the range."""
    frame = _read("SELECT s.id, s.task_id, s.title, s.done FROM steps s "
                  "JOIN tasks t ON t.id = s.task_id "
                  "WHERE COALESCE(t.done_on, t.day) BETWEEN :first AND :last "
                  "ORDER BY s.task_id, s.id",
                  first=first.isoformat(), last=last.isoformat())
    frame["done"] = frame["done"].astype(bool)
    return frame


def add_step(task_id: int, title: str) -> None:
    """Add a step to a task. A step never changes its task's own state."""
    if title := title.strip():
        _write("INSERT INTO steps (task_id, title, done) VALUES (:task_id, :title, 0)",
               task_id=task_id, title=title)


def delete_step(step_id: int) -> None:
    _write("DELETE FROM steps WHERE id = :id", id=step_id)


def set_step_done(step_id: int, done: bool) -> None:
    """Tick one step off, or untick it. Never touches the task's own state."""
    _write("UPDATE steps SET done = :done WHERE id = :id",
           id=step_id, done=int(bool(done)))


# --- Days -------------------------------------------------------------------

def days_in(first: date, last: date) -> pd.DataFrame:
    return _read("SELECT day, start_time, end_time, break_hours, comment, holiday "
                 "FROM days "
                 "WHERE day BETWEEN :first AND :last ORDER BY day",
                 first=first.isoformat(), last=last.isoformat())


def save_day(day: date, start: time | None, end: time | None,
             break_hours: float | None, comment: str | None,
             holiday: bool = False) -> None:
    """Upsert one day's record."""
    _write("INSERT INTO days (day, start_time, end_time, break_hours, comment, "
           "holiday) VALUES (:day, :start_time, :end_time, :break_hours, "
           ":comment, :holiday) "
           "ON CONFLICT (day) DO UPDATE SET start_time = :start_time, "
           "end_time = :end_time, break_hours = :break_hours, "
           "comment = :comment, holiday = :holiday",
           day=day.isoformat(), break_hours=break_hours,
           comment=comment or None, holiday=int(bool(holiday)),
           start_time=start.strftime("%H:%M") if start else None,
           end_time=end.strftime("%H:%M") if end else None)


# --- Weekly review ----------------------------------------------------------

def all_days() -> pd.DataFrame:
    """Every day ever recorded, for the archive."""
    return _read("SELECT day, start_time, end_time, break_hours, comment, holiday "
                 "FROM days "
                 "ORDER BY day")


def completed_tasks() -> pd.DataFrame:
    """Every finished task, under the day it was finished."""
    return _read("SELECT t.id, t.title, t.day, t.done_on, p.name AS project, "
                 "p.colour AS colour, " + _STEP_COUNTS
                 + _FROM_TASKS
                 + "WHERE t.done_on IS NOT NULL ORDER BY t.done_on, t.id")


def all_reviews() -> pd.DataFrame:
    """Every review answer ever saved, including ones whose question has since
    been reworded - the archive still shows them as they were asked."""
    return _read("SELECT week_start, question, answer FROM reviews "
                 "ORDER BY week_start, question")


def review(week_start: date) -> dict[str, str]:
    """The answers already given for a week, keyed by question."""
    frame = _read("SELECT question, answer FROM reviews WHERE week_start = :week",
                  week=week_start.isoformat())
    return dict(zip(frame["question"], frame["answer"].fillna("")))


def save_review(week_start: date, answers: dict[str, str]) -> None:
    with _conn().session as session:
        for question, answer in answers.items():
            session.execute(
                text("INSERT INTO reviews (week_start, question, answer) "
                     "VALUES (:week, :question, :answer) ON CONFLICT "
                     "(week_start, question) DO UPDATE SET answer = :answer"),
                {"week": week_start.isoformat(), "question": question,
                 "answer": answer.strip() or None})
        session.commit()
