"""One week in figures and one chart: what it added up to, and the shape of each
day. Drawn the same under My Week and in the archive."""

from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import db
from worktime import (WEEK_DAYS, WEEK_HOURS, clock, day_hours, expected, field,
                      is_holiday, totals, week_records, with_defaults)

#: A quiet grey for the labels and a lighter one for the guides.
LABEL, GREY = "#6F6757", "#B4AC9C"


def _toward_page(colour: str, amount: float) -> str:
    """`colour` mixed that far toward the page behind it."""
    page = st.get_option("theme.backgroundColor")
    parts = ((int(colour[i:i + 2], 16), int(page[i:i + 2], 16)) for i in (1, 3, 5))
    return "#" + "".join(f"{round(c + (p - c) * amount):02X}" for c, p in parts)


#: The bars take the theme's own accent, the colour a ticked checkbox uses, and
#: the break inside them the same colour part way to the page.
BAR = st.get_option("theme.primaryColor")
BREAK = _toward_page(BAR, 0.55)

#: An ordinary day, marked so a bar reads against it at a glance.
ORDINARY = (9, 17)

#: The bars' rounded corners. The break sits at the top of one, so it carries
#: the same radius there and squares off where it meets the hours below.
RADIUS = 5

#: The metric keeps its parts in an inner wrapper; that is what lays out, so the
#: overtime can sit beside the hours rather than under them.
CARD_CSS = """<style>
.st-key-hours-card [data-testid="stMetric"] > div {
    display: grid; grid-template-columns: auto 1fr;
    align-items: baseline; column-gap: 12px;
}
.st-key-hours-card [data-testid="stMetricLabel"] { grid-column: 1 / -1; }
.st-key-hours-card [data-testid="stMetricValue"] { grid-column: 1; }
.st-key-hours-card div:has(> [data-testid="stMetricDelta"]) { grid-column: 2; }
</style>"""


def _week_frame(week_start: date, saved: dict) -> pd.DataFrame:
    """One row a day, as the week's cards show it: an untouched weekday counts
    as an ordinary one, a weekend counts only what was put on it."""
    rows = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        record = saved.get(day)
        if day.weekday() < WEEK_DAYS:
            record = with_defaults(day, record)
        # A label, not a date: a temporal axis spreads one week over its hours.
        # An empty weekend still gets a row, so the plot shows the whole week.
        entry = {"Day": f"{day:%a %d}", "Start": None, "End": None,
                 "Worked": None, "Break": 0.0}
        if record is not None and not is_holiday(record):
            start, end = (clock(field(record, "start_time")),
                          clock(field(record, "end_time")))
            entry["Start"] = None if not start else start.hour + start.minute / 60
            entry["End"] = None if not end else end.hour + end.minute / 60
            entry["Worked"] = day_hours(record)
            entry["Break"] = field(record, "break_hours") or 0.0
        rows.append(entry)
    return pd.DataFrame(rows)


def _cards(week_start: date, saved: dict, filed: pd.DataFrame) -> None:
    """What the week added up to: the hours, then what was finished."""
    finished = filed[filed["done_on"].notna()]["kind"].value_counts()
    # An unfilled weekday counts as the ordinary day its card is showing.
    counted = week_records(week_start, saved)
    hours, breaks, overtime = totals(counted)
    owed = expected(counted)

    overtime_help = (f"Overtime, against the {owed:g} h this week owes"
                     + (f" ({WEEK_HOURS:g} h, less any holiday)."
                        if owed != WEEK_HOURS else "."))

    # The hours on one row, then what was finished on the next.
    rows = ([("Hours worked", f"{hours:.1f} h", f"{overtime:+.1f} h"),
             ("Break", f"{breaks:.1f} h", None)],
            [(label, int(finished.get(kind, 0)), None)
             for kind, label in ((db.TASK, "Tasks completed"),
                                 (db.MEETING, "Meetings completed"),
                                 (db.PAPER, "Papers read"))])
    for row in rows:
        for column, (label, value, delta) in zip(st.columns(len(row)), row):
            # Only the card with a delta needs the frame that lays it out.
            holder = column.container(key="hours-card") if delta else column
            holder.metric(label, value, delta=delta, border=True,
                          help=overtime_help if delta else None)
    st.html(CARD_CSS)


def _chart(week: pd.DataFrame, height: int) -> None:
    """One bar a day, from the hour it started to the hour it ended, with the
    hours actually worked - the span less the break - written above it."""
    clocked = week.dropna(subset=["Start", "End"])
    if clocked.empty:
        return

    # The bars take their width from the band rather than a fixed size, or they
    # run into one another as the window narrows.
    day = alt.X("Day:N", sort=None, title=None,
                scale=alt.Scale(domain=list(week["Day"]),
                                paddingInner=0.4, paddingOuter=0.3),
                axis=alt.Axis(labelAngle=0))

    tips = [alt.Tooltip("Day:N"), alt.Tooltip("Start:Q", format=".2f"),
            alt.Tooltip("End:Q", format=".2f"),
            alt.Tooltip("Worked:Q", title="Worked", format=".2f"),
            alt.Tooltip("Break:Q", title="Break", format=".2f")]

    span = alt.Chart(clocked).mark_bar(cornerRadius=RADIUS, color=BAR).encode(
        x=day,
        y=alt.Y("Start:Q", title=None,
                scale=alt.Scale(zero=False, nice=False, padding=12),
                axis=alt.Axis(labels=False)),
        y2="End:Q",
        tooltip=tips)

    # A day records how long the break was, never when it was taken, so it is
    # drawn at the end of the day: the size is the fact, the placement a reading.
    taken = clocked[clocked["Break"] > 0].copy()
    taken["BreakEnd"] = taken["End"]
    taken["BreakStart"] = (taken["End"]
                           - taken["Break"].clip(upper=taken["End"] - taken["Start"]))
    rest = alt.Chart(taken).mark_bar(
        cornerRadiusTopLeft=RADIUS, cornerRadiusTopRight=RADIUS,
        color=BREAK).encode(
        x=day, y="BreakStart:Q", y2="BreakEnd:Q", tooltip=tips)

    marks = pd.DataFrame({"hour": list(ORDINARY)})
    guides = alt.Chart(marks).mark_rule(
        color=GREY, strokeDash=[4, 4], strokeWidth=0.8).encode(y="hour:Q")
    # In the margin, not the plot: anywhere inside it could land on a bar.
    guide_labels = alt.Chart(marks).transform_calculate(
        label="format(datum.hour, '02') + ':00'").mark_text(
        align="right", dx=-6, fontSize=10, font="Inter", color=GREY,
        clip=False).encode(x=alt.value(0), y="hour:Q", text="label:N")

    worked = alt.Chart(clocked).transform_calculate(
        label="format(datum.Worked, '.1f') + ' h'").mark_text(
        dy=-9, fontSize=10, font="Inter", color=LABEL).encode(
        x=day, y="End:Q", text="label:N")

    st.altair_chart(
        (guides + guide_labels + span + rest + worked).properties(
            width="container", height=height,
            padding={"left": 44, "top": 5, "right": 5, "bottom": 5})
        .configure_view(strokeWidth=0)
        .configure_axis(labelFont="Inter", titleFont="Inter", labelColor=LABEL,
                        titleColor=LABEL, labelFontSize=11, domain=False,
                        ticks=False, grid=False, labelPadding=8)
        .configure_axisY(grid=False))


def render(week_start: date, saved: dict, filed: pd.DataFrame,
           height: int = 410) -> None:
    """The cards and the plot for one week, from what the page has already read
    of it: the days it holds, and everything filed against them."""
    _cards(week_start, saved, filed)
    _chart(_week_frame(week_start, saved), height)
