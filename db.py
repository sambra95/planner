"""Every read and write the planner makes.

One SQL connection, the three tables behind it, and small helpers the pages call.
Postgres is the deployment target; with no connection configured the app falls
back to a local SQLite file so it still runs on a laptop.

Dates cross this boundary as ISO strings and come back as pandas datetimes, so
the two dialects behave identically above this module.
"""

from __future__ import annotations

from datetime import date, time

import pandas as pd
import streamlit as st
from sqlalchemy import text

LOCAL_URL = "sqlite:///planner.db"

_DATE_COLUMNS = ("day", "done_on", "created_on", "week_start")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id         {id_column},
    title      TEXT NOT NULL,
    day        DATE,
    done_on    DATE,
    created_on DATE NOT NULL
);
CREATE TABLE IF NOT EXISTS days (
    day         DATE PRIMARY KEY,
    start_time  TEXT,
    end_time    TEXT,
    focus_hours REAL,
    comment     TEXT
);
CREATE TABLE IF NOT EXISTS reviews (
    week_start DATE NOT NULL,
    question   TEXT NOT NULL,
    answer     TEXT,
    PRIMARY KEY (week_start, question)
);
"""


def is_local() -> bool:
    """True when no Postgres connection is configured and SQLite is standing in."""
    try:
        return "planner" not in st.secrets.get("connections", {})
    except Exception:
        return True


@st.cache_resource(show_spinner=False)
def _create_tables(_connection) -> None:
    """Create anything missing, once per session. The argument is underscored so
    Streamlit caches on the call rather than trying to hash the connection."""
    serial = ("INTEGER PRIMARY KEY AUTOINCREMENT"
              if _connection.engine.dialect.name == "sqlite" else "SERIAL PRIMARY KEY")
    with _connection.session as session:
        for statement in _SCHEMA.format(id_column=serial).strip().split(";"):
            if statement.strip():
                session.execute(text(statement))
        session.commit()


def _conn():
    """The connection (``st.connection`` caches it), with its tables in place."""
    conn = (st.connection("planner_local", type="sql", url=LOCAL_URL) if is_local()
            else st.connection("planner", type="sql"))
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


def _iso(value) -> str | None:
    """A date-ish value as 'YYYY-MM-DD', or None when it is blank."""
    if value is None or value == "" or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


# --- Tasks ------------------------------------------------------------------

def open_tasks() -> pd.DataFrame:
    """Everything still to do, oldest assigned day first, unassigned last.

    A task assigned to a past day is simply still open, so it appears here again
    on its own - the day it was meant for is kept, and shown as pushed forward.
    """
    frame = _read("SELECT id, title, day FROM tasks WHERE done_on IS NULL "
                  "ORDER BY day IS NULL, day, id")
    frame.insert(0, "done", False)
    today = pd.Timestamp(date.today())
    frame["status"] = ["Pushed forward" if day < today else "" for day in
                       frame["day"].fillna(today)]
    return frame


def save_task_edits(delta: dict, frame: pd.DataFrame) -> None:
    """Apply one round of `st.data_editor` changes: additions, edits, deletions."""
    today = date.today().isoformat()
    with _conn().session as session:
        for row in delta.get("added_rows", []):
            if title := (row.get("title") or "").strip():
                day = _iso(row.get("day"))
                session.execute(
                    text("INSERT INTO tasks (title, day, done_on, created_on) "
                         "VALUES (:title, :day, :done_on, :created_on)"),
                    {"title": title, "day": day, "created_on": today,
                     "done_on": (day or today) if row.get("done") else None})
        for index, changes in delta.get("edited_rows", {}).items():
            row = frame.iloc[int(index)]
            day = _iso(changes["day"]) if "day" in changes else _iso(row["day"])
            done = changes.get("done", bool(row["done"]))
            session.execute(
                text("UPDATE tasks SET title = :title, day = :day, done_on = :done_on "
                     "WHERE id = :id"),
                {"id": int(row["id"]), "day": day,
                 "title": (changes.get("title") or row["title"]).strip(),
                 "done_on": (day or today) if done else None})
        for index in delta.get("deleted_rows", []):
            session.execute(text("DELETE FROM tasks WHERE id = :id"),
                            {"id": int(frame.iloc[int(index)]["id"])})
        session.commit()


def tasks_in(first: date, last: date) -> pd.DataFrame:
    """Tasks assigned to any day in the range, done or not."""
    return _read("SELECT id, title, day, done_on FROM tasks "
                 "WHERE day BETWEEN :first AND :last ORDER BY id",
                 first=first.isoformat(), last=last.isoformat())


def set_task_done(task_id: int, day: date | None) -> None:
    """Tick a task off on `day`, or untick it when `day` is None."""
    _write("UPDATE tasks SET done_on = :done_on WHERE id = :id",
           id=task_id, done_on=day.isoformat() if day else None)


# --- Days -------------------------------------------------------------------

def days_in(first: date, last: date) -> pd.DataFrame:
    return _read("SELECT day, start_time, end_time, focus_hours, comment FROM days "
                 "WHERE day BETWEEN :first AND :last ORDER BY day",
                 first=first.isoformat(), last=last.isoformat())


def save_day(day: date, start: time | None, end: time | None,
             focus_hours: float | None, comment: str | None) -> None:
    """Upsert one day's record; the same statement works on Postgres and SQLite."""
    _write("INSERT INTO days (day, start_time, end_time, focus_hours, comment) "
           "VALUES (:day, :start_time, :end_time, :focus_hours, :comment) "
           "ON CONFLICT (day) DO UPDATE SET start_time = :start_time, "
           "end_time = :end_time, focus_hours = :focus_hours, comment = :comment",
           day=day.isoformat(), focus_hours=focus_hours, comment=comment or None,
           start_time=start.strftime("%H:%M") if start else None,
           end_time=end.strftime("%H:%M") if end else None)


# --- Weekly review ----------------------------------------------------------

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
                     "VALUES (:week, :question, :answer) "
                     "ON CONFLICT (week_start, question) DO UPDATE SET answer = :answer"),
                {"week": week_start.isoformat(), "question": question,
                 "answer": answer.strip() or None})
        session.commit()
