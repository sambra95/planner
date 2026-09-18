# Planner

A personal task list, work diary and weekly review, built with Streamlit.

- **My Week** — the calendar, a week at a time: start and end times, the break
  taken between them (which comes off the hours worked), the day's checklist and
  a comment box, with hours worked, break and overtime on top. A day you have not
  filled in shows an ordinary nine to five with the break that leaves exactly a
  contracted day, and is counted as one until you say otherwise. Tick a day as a
  holiday and it drops out
  of every time calculation — it stops counting as a day you were expected to
  work, so it neither earns nor costs overtime. Overtime is the week's hours
  against a contracted week of 7.4 h × 5. A weekday you have not filled in
  counts as the ordinary day its card shows, so an untouched week reads as
  square rather than 37 hours short. A weekend counts only what you put on it,
  and shows nothing by default. Breaks are already off the hours worked, so a
  break neither earns overtime nor is owed back. A day lists what is on it as a
  name in its project's colour; click one to open it and edit it — title, day,
  project, description, and either its steps, a meeting's times and write-up, or
  a paper's comments. Anything on a day can be taken off it without being
  deleted: a task
  goes back to the open list, a paper back to the Papers page. A meeting is the
  exception — it only exists on its day, so taking it off calls it off, and it
  asks first. Everything saves as you type it.
- **Tasks** — every open task, one card each, holding its project, day, optional
  description, steps and delete button together. The list runs newest first, so a
  task you have just added is at the top. Give a task a day and it turns up in
  that day's checklist, and once that day is past it is recorded as done on it
  and goes to the archive — a day you have had is a day you have had. A task with
  no day simply waits here.
- **Steps** — break a task into steps with the box under it, tick them as you go,
  remove one with the cross beside it. Steps are independent: ticking every one
  of them does *not* finish the task. Only the task's own checkbox does that, and
  that decides the day it is archived under — today when you tick it on the
  Tasks page, or that day when you tick it on a day's card in My Week.
- **Meetings** — made on the Meetings page, not in the task list, and kept off
  it. The page is a month calendar: each meeting sits on its day, in its
  project's colour, and a day holding more than fit is badged with its total.
  Click one to open it and change its title, day or project, give it optional
  start and finish times, or write it up under Goals, Comments and Action points.
  A meeting with times shows them on its chip, in the calendar and in the day's
  checklist. A meeting also appears in that day's checklist in My Week, where
  it can be ticked off as you hold it — and if you never tick it, it settles as
  held on its own day once that day is over, the same way a task does.
- **Papers** — added on the Papers page and kept off the task list. A paper
  starts with no day; give it one and it turns up in that day's checklist like
  anything else, but it has no steps — just a box for your comments. Tick it off
  once you have read it and it goes to the archive, comments and all, under the
  day you read it. A paper is the one thing a passing day does not settle: an
  unread paper is not read just because the day you set aside for it has gone.
- **Review** — four questions at the end of each week. From Friday the app shows
  a reminder on every page until that week is answered; earlier in the week it
  reminds you about the week just gone.
- **Projects** — a name and an optional description, laid out like the task list.
  Each project is given a colour of its own, automatically: the first not already
  in use, and a colour freed by a deletion is reused. Anything assigned to a
  project is badged in its colour and its card is tinted to match. Deleting a
  project releases its tasks rather than deleting them. Archive one instead and
  it retires to a section at the bottom of the page: it and everything still
  assigned to it turn grey, and the colour it was using goes back into
  circulation for the next project. Restoring it takes whatever colour is free
  then.
- **Archive** — papers first, in their own section: a searchable table of what
  you have read, whatever week it happened in. The search matches titles,
  comments and projects, and picking a row opens the paper to read or edit your
  comments. Below that, every week you have recorded, summarised in one table —
  hours, break, overtime, tasks finished and whether it was reviewed.
  Open any week and its days are laid out exactly as My Week draws them,
  with the review you wrote underneath. Untick a task there to put it back on the
  open list, which is how a task ticked off by mistake is undone.

Each day keeps a permanent record of its start and end time, break,
comment and the tasks completed on it, and every weekly review is kept too. A
finished task is filed under the day it was finished, not the day it was planned
for, and it drops out of the editable task list at that point, so nothing later
rewrites what a past day says. A task still open moves freely until it is done.

## Running it locally

```bash
uv sync
.venv/bin/streamlit run streamlit_app.py
```

`pyproject.toml` is the source of truth for dependencies and `uv sync` resolves
it into `uv.lock`, which is committed. Streamlit Cloud reads `uv.lock` before
any other dependency file, so the deployed app gets exactly the versions pinned
here. `requirements.txt` is a hand-kept mirror for `pip`, and Cloud ignores it.

With no database configured the app writes to `planner.db` (SQLite) in this
folder. Nothing on screen says so, so check your secrets are set before trusting
a deployment to be saving anywhere permanent.

## Deploying privately on Streamlit Cloud

Streamlit Cloud wipes its filesystem whenever the app restarts, so it needs a
real database.

1. Create a free Postgres database — [Neon](https://neon.tech) or
   [Supabase](https://supabase.com) — and copy its connection string.
2. Push this folder to a **private** GitHub repository.
3. Deploy it at [share.streamlit.io](https://share.streamlit.io), pointing at
   `streamlit_app.py`.
4. In the app's **Settings → Secrets**, paste the block from
   `.streamlit/secrets.toml.example` with your own connection string:

   ```toml
   [connections.planner]
   url = "postgresql+psycopg2://USER:PASSWORD@HOST/DATABASE?sslmode=require"
   ```

5. Under **Settings → Sharing**, keep the app private to your own account.

The three tables are created on first run. To work against Postgres locally too,
put the same block in `.streamlit/secrets.toml` — it is git-ignored, as is
`planner.db`.

## Changing things

- Contracted hours per day and days per week (`7.4` × `5`, which overtime is
  measured against), and the nine-to-five a blank day starts out showing:
  `STANDARD_DAY`, `WEEK_DAYS`, `DEFAULT_START` and `DEFAULT_END` at the top of
  `worktime.py`. The default break is derived from them, so it
  always leaves exactly a contracted day.
- The size of a day in the meetings calendar: `CELL_HEIGHT` at the top of
  `app_pages/meetings.py`. Every day is the same height; a day with more
  meetings than fit is badged with its total and scrolls inside its own cell.
- The colours projects are drawn from, and the order they are handed out:
  `COLOURS` in `palette.py`. These are Streamlit's own badge colours, so they
  follow the theme in light and dark.
- The weekly questions: `QUESTIONS` at the top of `app_pages/review.py`. Answers
  already saved keep the wording they were asked under, so past weeks still read
  correctly after a reword.
- Colours and fonts: `.streamlit/config.toml`. The size and spread of the top
  tabs, and the divider under them, are `NAV_CSS` in `palette.py`.

## Layout

```
streamlit_app.py     navigation, the app-wide styling, the end-of-week reminder
db.py                every read and write, and the schema behind them
worktime.py          the hours arithmetic both the week and archive need
daycard.py           one day's card, as the week view and the archive draw it
palette.py           project colours, and how a project reads as a badge
pyproject.toml       dependencies; uv.lock is what Cloud installs from
app_pages/
    week.py          the week calendar, shown as the My Week tab
    tasks.py         the open task list
    projects.py      projects and their colours
    meetings.py      meetings by month, with their write-ups
    papers.py        papers to read, and what you thought of them
    review.py        the weekly questions
    archive.py       past weeks, summarised
```
