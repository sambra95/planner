# Planner

A personal task list, work diary and weekly review. Runs on your Mac or PC,
keeps everything in one SQLite file, and talks to nothing.

[![Download Planner for macOS](https://img.shields.io/github/v/release/sambra95/planner?display_name=tag&style=for-the-badge&logo=apple&logoColor=white&label=Download%20for%20macOS&color=0b7285)](https://github.com/sambra95/planner/releases/latest/download/Planner-macos-arm64.dmg)
[![Download Planner for Windows](https://img.shields.io/github/v/release/sambra95/planner?display_name=tag&style=for-the-badge&logo=windows&logoColor=white&label=Download%20for%20Windows&color=0b7285)](https://github.com/sambra95/planner/releases/latest/download/Planner-windows-x64.zip)

**macOS** - open the disk image. A window appears with **Planner** beside the
Applications folder: drag one onto the other. The first launch needs
right-click → Open, because the bundle is ad-hoc signed rather than notarised.
Apple silicon only.

**Windows** - unzip the folder wherever you want it and double-click
**Planner.cmd** inside. Right-click it → *Show more options* → *Send to* →
*Desktop* for a shortcut. SmartScreen may ask once: *More info* → *Run anyway*.
64-bit only.

Either way the app carries its own Python, so nothing else needs installing. It
opens in your browser and quits about thirty seconds after you close the last
tab.

## The tabs

- **My Week** - the calendar a week at a time: start and end times, the break
  between them, each day's checklist and a comment, with the week's totals on
  top. A blank weekday shows an ordinary nine to five and counts as one, so an
  untouched week reads as square; overtime is measured against 7.4 h × 5, less a
  day for each weekday marked as holiday. Click anything on a day to open and
  edit it, or take it off the day without deleting it.
- **Tasks** - everything still to do, newest first. Each task is one card with
  its project, day, optional description and milestones. Milestones are
  independent: ticking them all does not finish the task, and only the task's
  own checkbox decides the day it is archived under. A milestone is ticked off
  on a day of its own, and that day's card records it however long the task
  itself stays open. A task still open when its day passes
  comes off that day and goes back on the list.
- **Meetings** - a month calendar. Each meeting sits on its day in its project's
  colour, with optional start and finish times; click one to write it up under
  Goals, Notes and Action points. Taking a meeting off its day calls it off.
- **Papers** - added here and kept off the task list. A paper starts with no day
  and has no milestones, just notes and keyword tags. Tick it off once read and it
  goes to the archive, where the tags make it findable.
- **Review** - four questions at the end of each week, with a reminder on the
  last working day that is not a holiday.
- **Projects** - a name, a description and a colour of its own, handed out
  automatically and never repeated. Archive one to retire it: it and everything
  assigned to it turn grey, and its colour returns to circulation.
- **Archive** - a searchable table of every paper read, then every week
  recorded, with its days and review.

Nothing is ever deleted behind your back: a finished item is filed under the day
it was finished, and unticking it puts it back.

## Where the data lives

One SQLite file, and only on this machine:

- packaged app, macOS - `~/Library/Application Support/Planner/planner.db`
- packaged app, Windows - `%LOCALAPPDATA%\Planner\planner.db`
- checkout - `planner.db` beside the code

Either way it sits outside the app, so replacing the app leaves your planner
alone. There is no copy anywhere else, so include it in whatever backs up your
home directory. The log sits beside the database on Windows, and in
`~/Library/Logs/Planner` on a Mac.
