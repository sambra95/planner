"""Work-hours arithmetic, shared by the week view and the archive."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd

#: Contracted hours in a working day, and the days a contracted week has.
#: Overtime is measured against the week, not against the days you filled in.
STANDARD_DAY = 7.4
WEEK_DAYS = 5
WEEK_HOURS = STANDARD_DAY * WEEK_DAYS

#: What a day starts out showing: an ordinary nine to five, with the break that
#: leaves exactly a contracted day's work. The break is derived rather than
#: typed in, so changing either the hours or the day length keeps them agreeing.
DEFAULT_START = time(9, 0)
DEFAULT_END = time(17, 0)


def monday_of(day: date) -> date:
    """The Monday that starts `day`'s week."""
    return day - timedelta(days=day.weekday())


def field(record, name: str):
    """One field of a day's record, with missing values as None."""
    value = record.get(name)
    return None if value is None or pd.isna(value) else value


def clock(value) -> time | None:
    """A stored 'HH:MM' string as a time."""
    return datetime.strptime(value, "%H:%M").time() if value else None


def span(start: time | None, end: time | None) -> float | None:
    """Hours between two clock times, or None when the day is not filled in."""
    if not (start and end):
        return None
    worked = datetime.combine(date.min, end) - datetime.combine(date.min, start)
    return max(0.0, worked.total_seconds() / 3600)


def is_holiday(record) -> bool:
    """A day marked as holiday, which no time calculation counts."""
    return bool(field(record, "holiday"))


def day_hours(record) -> float | None:
    """Hours actually worked on one day: the span between start and end, less any
    break taken within it. None when the day is a holiday, or has no times."""
    if is_holiday(record):
        return None
    return net(span(clock(field(record, "start_time")),
                    clock(field(record, "end_time"))),
               field(record, "break_hours"))


def default_break() -> float:
    """The break that turns the default day into a contracted day's work."""
    return round(span(DEFAULT_START, DEFAULT_END) - STANDARD_DAY, 2)


def when(record) -> str:
    """A meeting's times as "09:00-10:00", or as much of it as is set."""
    start, end = field(record, "start_time"), field(record, "end_time")
    return f"{start}–{end}" if start and end else (start or end or "")


def or_default(value, fallback):
    """`value` unless it was never set. A recorded zero is a value, not a gap."""
    return fallback if value is None else value


def net(worked: float | None, taken: float | None) -> float | None:
    """Time between start and end, less the break taken within it."""
    if worked is None:
        return None
    return max(0.0, worked - (taken or 0.0))


def default_record(day: date) -> dict:
    """What a weekday nobody has filled in stands for: an ordinary day."""
    return {"day": pd.Timestamp(day),
            "start_time": DEFAULT_START.strftime("%H:%M"),
            "end_time": DEFAULT_END.strftime("%H:%M"),
            "break_hours": default_break(), "holiday": 0}


def with_defaults(day: date, record) -> dict:
    """A weekday's record with anything left blank standing in as an ordinary
    day - which is exactly what its card is showing. A holiday is left alone:
    nothing is expected of it."""
    ordinary = default_record(day)
    if record is None:
        return ordinary
    if is_holiday(record):
        return record
    filled = dict(record)
    for part in ("start_time", "end_time", "break_hours"):
        if field(record, part) is None:
            filled[part] = ordinary[part]
    return filled


def week_records(week_start: date, saved: dict) -> list:
    """The week's records for counting: what was saved, with every weekday's
    gaps filled in as an ordinary day.

    The cards show an unfilled weekday as an ordinary nine to five, so the
    totals count it as one rather than reading the week as short. A weekend
    counts only what was actually put on it: no work is expected there.
    """
    week = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        record = saved.get(day)
        if day.weekday() < WEEK_DAYS:
            week.append(with_defaults(day, record))
        elif record is not None:
            week.append(record)
    return week


def is_weekday(record) -> bool:
    """A day the week expects work on. A weekend is its own affair."""
    day = field(record, "day")
    return day is not None and pd.Timestamp(day).weekday() < WEEK_DAYS


def expected(records) -> float:
    """Hours a week owes: a full contracted week, less a day for each weekday
    taken as holiday. A holiday at the weekend changes nothing, because no work
    was expected then anyway."""
    off = sum(1 for record in records
              if is_holiday(record) and is_weekday(record))
    return max(0.0, STANDARD_DAY * (WEEK_DAYS - off))


def totals(records) -> tuple[float, float, float]:
    """Hours worked, break hours and overtime across one week of day records.

    Hours worked are already net of breaks, so a break neither earns overtime
    nor is owed back. Overtime is what the week worked less what the week owed,
    so a week you only half filled in reads as short rather than as square.
    Holidays are left out of the hours and taken off what is owed.
    """
    records = list(records)
    working = [record for record in records if not is_holiday(record)]
    hours = [value for value in map(day_hours, working) if value is not None]
    idle = [field(record, "break_hours") for record in working]
    return (sum(hours), sum(value for value in idle if value),
            sum(hours) - expected(records))
