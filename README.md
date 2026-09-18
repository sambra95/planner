# Planner

A personal task list, work diary and weekly review. Runs on your Mac, keeps
everything in one SQLite file, and talks to nothing.

[![Download for macOS](https://img.shields.io/badge/Download-Planner%20for%20macOS-0b7285?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/sambra95/planner/releases/latest/download/Planner-macos-arm64.zip)

Unzip it and drag **Planner** to Applications. Or install it in one line:

```bash
curl -L https://github.com/sambra95/planner/releases/latest/download/Planner-macos-arm64.zip \
  -o /tmp/Planner.zip
ditto -x -k /tmp/Planner.zip ~/Applications && rm /tmp/Planner.zip
```

The app carries its own Python, so nothing else needs installing. It opens in
your browser and quits about thirty seconds after you close the last tab. The
first launch needs right-click → Open, because the bundle is ad-hoc signed
rather than notarised. Apple silicon only.

## The tabs

- **My Week** - the calendar a week at a time: start and end times, the break
  between them, each day's checklist and a comment, with the week's totals on
  top. A blank weekday shows an ordinary nine to five and counts as one, so an
  untouched week reads as square; overtime is measured against 7.4 h × 5, less a
  day for each weekday marked as holiday. Click anything on a day to open and
  edit it, or take it off the day without deleting it.
- **Tasks** - everything still to do, newest first. Each task is one card with
  its project, day, optional description and steps. Steps are independent:
  ticking them all does not finish the task, and only the task's own checkbox
  decides the day it is archived under. A task whose day has passed settles onto
  that day by itself.
- **Meetings** - a month calendar. Each meeting sits on its day in its project's
  colour, with optional start and finish times; click one to write it up under
  Goals, Comments and Action points. Taking a meeting off its day calls it off.
- **Papers** - added here and kept off the task list. A paper starts with no day
  and has no steps, just comments. Tick it off once read and it goes to the
  archive.
- **Review** - four questions at the end of each week, with a reminder from
  Friday until they are answered.
- **Projects** - a name, a description and a colour of its own, handed out
  automatically and never repeated. Archive one to retire it: it and everything
  assigned to it turn grey, and its colour returns to circulation.
- **Archive** - a searchable table of every paper read, then every week
  recorded, with its days and review.

Nothing is ever deleted behind your back: a finished item is filed under the day
it was finished, and unticking it puts it back.

## Where the data lives

One SQLite file, and only on this machine:

- packaged app - `~/Library/Application Support/Planner/planner.db`, so
  replacing the app leaves your planner alone
- checkout - `planner.db` beside the code

There is no copy anywhere else, so include it in whatever backs up your home
directory. Logs are in `~/Library/Logs/Planner`.

## Running from a checkout

```bash
uv sync
.venv/bin/streamlit run streamlit_app.py
```

## Building the app

```bash
./scripts/make_dist.sh --version 1.0.0        # Planner.app and a .zip
./scripts/make_dist.sh --version 1.0.0 --xz   # also a .tar.xz, half the size
```

Built for the architecture of the machine you run it on. The build trims what a
packaged Streamlit app never touches and strips debug symbols, taking the app
from 352 MB to 211 MB. Signing comes last on purpose: stripping removes a
signature, and arm64 macOS kills unsigned code rather than loading it.

`dist/` is git-ignored, so a release is how a build gets out, and that is
automatic: push a tag and `.github/workflows/release.yml` builds on a macOS
runner and attaches both archives to the release, which the link at the top
then picks up.

```bash
git tag -a v1.0.1 -m "Planner 1.0.1" && git push origin v1.0.1
```

The tag sets the version in `Info.plist`. Building locally is only for testing.

## Changing things

| What                                                         | Where                                                                        |
| ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Hours a day and days a week, and the times a blank day shows | `STANDARD_DAY`, `WEEK_DAYS`, `DEFAULT_START`, `DEFAULT_END` in `worktime.py` |
| Project colours                                              | `PALETTE` in `palette.py`                                                    |
| The weekly questions                                         | `QUESTIONS` in `app_pages/review.py`                                         |
| Day size in the meetings calendar                            | `CELL_HEIGHT` in `app_pages/meetings.py`                                     |
| Colours, fonts, the tab bar                                  | `.streamlit/config.toml` and `NAV_CSS` in `palette.py`                       |

## Layout

```
streamlit_app.py     navigation, app-wide styling, the end-of-week reminder
db.py                every read and write, and the schema behind them
daycard.py           one day's card, shared by My Week and the archive
worktime.py          hours arithmetic
palette.py           project colours and the CSS built from them
bootstrap.py         entry point for the packaged app
app_pages/           one file per tab
scripts/make_dist.sh builds the portable macOS bundle
.github/workflows/  builds and publishes a release from a tag
```
