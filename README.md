# Planner

A personal task list, work diary and weekly review, built with Streamlit.

- **Tasks** — every open task in one editable table. Give a task a day and it
  turns up in that day's checklist. Anything still open after its day comes back
  to the list marked *pushed forward*.
- **Week** — the calendar, a week at a time: start and end times, focused hours,
  the day's checklist and a comment box, with hours worked, focused hours and
  overtime across the top. Everything saves as you type it.
- **Review** — four questions at the end of each week. From Friday the app shows
  a reminder on every page until that week is answered; earlier in the week it
  reminds you about the week just gone.

## Running it locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run streamlit_app.py
```

With no database configured the app writes to `planner.db` (SQLite) in this
folder and says so under the title.

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

- Contracted hours per day (`7.4`, used for overtime): `STANDARD_DAY` at the top
  of `app_pages/week.py`.
- The weekly questions: `QUESTIONS` at the top of `app_pages/review.py`. Answers
  already saved keep the wording they were asked under, so past weeks still read
  correctly after a reword.
- Colours and fonts: `.streamlit/config.toml`.

## Layout

```
streamlit_app.py     navigation, the title, and the end-of-week reminder
db.py                every read and write, and the schema behind them
app_pages/
    tasks.py         the open task list
    week.py          the week calendar
    review.py        the weekly questions
```
