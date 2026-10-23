# Kanban TUI

A modern terminal Kanban board (Python + [Textual](https://textual.textualize.io/))
where every task is a plain markdown file, so the board can be synced across
machines with MEGA (or Dropbox, Syncthing, git, etc.). The interface (labels,
dialogs, column headers) is in Spanish; this doc stays in English for
development notes.

## Look & feel

The board renders as one big minimalist table rather than boxed cards: each
task is a single compact row (icon, title, priority, due date, labels — like
an email client's inbox list), with no per-column or per-lane scrolling.
Every lane and column grows (height) to fit its tallest column/lane
automatically as the backlog grows; the whole board scrolls as one page.
Color scheme is a dark amber/orange terminal palette (scrollbars included).

The task and objectives popups are sized to fit all their fields on a
normal terminal without an inner scrollbar; on a very short terminal they'll
still scroll as a fallback rather than clip content.

Column titles (`PENDIENTES` / `EN PROGRESO` / `HECHO`) are printed once, in a
pinned header row at the top of the dashboard — they aren't repeated per
lane. A single horizontal rule separates one lane from the next (brighter
when that lane is the active one); task rows within a lane keep a consistent,
tight vertical rhythm with no extra spacing. Each lane's own title line
carries its per-column counts and WIP ratio instead (e.g.
`🎯 General · P3 · Pend 2 · Prog 1/1 · Hecho 4 · esta semana: 2`).

Each task row is three lines: the compact title/meta line, then two tree
nodes —

```
🔥 Fix production outage on payments API   P0   vencida 2026-10-10   bug
 |_ Payments API is returning 500s intermittently.
 |_ 500s drop below 0.1% for 15 straight minutes.
```

— `|_` Resumen (a one-line preview of the description) and `|_` Criterio de
aceptación (acceptance criteria). Both are truncated with `…` rather than
wrapped, so every card stays exactly 3 rows tall. Press `s` for the full,
untruncated text of every task in the active lane (see
[Objective summary](#objective-summary-s)).

## Swimlanes

The board is organized in horizontal **lanes**:

- **Urgencias** — a fixed lane at the top, always visible, that only ever
  shows tasks of the Expedite service class.
- One lane per **objective**, up to **4 active objectives** at a time (press
  `o` to manage them: create, close, reopen, reprioritize — see
  [Keybindings](#keybindings)). Closing a lane archives its objective and
  hides it from the board; its tasks stay on disk and are visible again if
  the objective is reopened.

Every objective requires a **description** when it's created (mandatory,
just like a task's acceptance criteria) and it's shown right on the
dashboard, as a muted line under the lane's title — no need to open the
objectives screen to remember what a lane is for.

Lanes are sorted by **objective priority** (0 = highest, shown first right
under Urgencias), then by creation date. Objective priority is independent
from each task's own `priority` field.

Each lane has its own `Backlog` → `Doing` → `Done` columns. A task's column
is just a `status` field inside its markdown frontmatter — the file never
moves or gets renamed when you change columns, which keeps sync tools happy
(no move/rename conflicts).

## Service classes

Every task (except Expedite ones) belongs to exactly one objective/lane and
has a service class:

- **Estándar** — default FIFO work, respects the lane's WIP limit strictly.
- **Fecha fija** — gains sort priority automatically as its due date gets
  close or passes.
- **Expedito** — true emergencies. Any number can sit queued in the
  Urgencias lane's Backlog, but only **2** can be in `Doing` at the same
  time — that cap is enforced only on the `Doing` column, same as any other
  lane's WIP.
- **Intangible** — important-but-not-urgent work; flagged on its card if it
  sits untouched for more than 30 days, as a nudge to re-triage it.

## WIP limit

Each objective lane enforces a **WIP of 1** in its `Doing` column (shown as
`Prog n/1` in the lane's title line, turning red at the limit); the
Urgencias lane enforces a **WIP of 2** in `Doing` instead (Expedito tasks
can pile up freely in Backlog — the limit only kicks in when moving one into
`Doing`). Creating or moving a task into Doing beyond the lane's limit is
blocked until another one moves on. The lane title also shows an
informational "esta semana: N" counter of tasks started that week — it's
not enforced, just a nudge to keep every lane moving.

## Due-date priority escalation

Every time the board loads or reloads (startup, pressing `r`, or picking up
an external file change), tasks with a due date and not yet Done get their
`priority` auto-raised the closer that date gets — it only ever makes a task
*more* important, never less, and leaves a task alone if you already gave it
a higher priority by hand:

- Due within **5 days** (or already overdue by less than that): priority is
  capped at **2** if it was lower priority (a higher number) than that.
- Due within **2 days**, or overdue: priority is capped at **0** (highest).

This is implemented in `storage.escalate_due_dates` and persists back to the
task's `.md` file, so the escalation is visible even outside the TUI.

## Metrics

Press `m` to open a read-only metrics screen: weekly throughput (last 8
weeks), average lead time and cycle time, current WIP per lane, and the
distribution of active tasks by service class.

## Objective summary (`s`)

Press `s` to open a read-only summary of the **active lane**: its stats
(Pendientes / En progreso / Hecho / Total), and every task in it with the
full, untruncated Resumen and Criterio de aceptación — the detail view for
the compact `|_` nodes shown on the board itself.

## Task file format

Each task is one `.md` file with YAML frontmatter:

```markdown
---
id: a1b2c3d4
title: Fix production outage on payments API
status: doing             # backlog | doing | done
service_class: expedite   # standard | fixed_date | expedite | intangible
objective: ""              # name of the objective/lane; empty for Expedite
priority: 0                # 0 (highest) .. 5 (lowest)
labels:
- bug
- backend
due_date: 2026-10-10        # optional; required only for fixed_date tasks
started_at:                 # set automatically the first time it enters Doing
completed_at:
created_at: 2026-10-08 09:15:00
updated_at: 2026-10-09 08:00:00
---

Free-form description goes here (the Resumen shown on the board).

## Criterio de aceptación

The acceptance criteria goes here. Mandatory in the UI — the form won't
save a task without it.
```

The body after the frontmatter holds the free-form description, and —
after the `## Criterio de aceptación` marker line — the acceptance
criteria. The form requires acceptance criteria for every task (new or
edited); older files without it just show "(sin criterio de aceptación)"
on the board until you fill it in.

Older files with a legacy `type: normal|deadline|urgent` field are migrated
transparently on read (`normal`→Estándar, `deadline`→Fecha fija,
`urgent`→Expedito) and rewritten in the new format the next time they're
saved.

## Alerts & board styling

Each card shows one alert state (checked in this order, only one applies):

1. **Expedito** — blinks slowly in **red**.
2. **Approaching due date** — due within 3 days and not done — blinks slowly
   in **yellow**.
3. **Overdue** — due date in the past and not done — solid red border (no
   blink).
4. **Low priority** (`priority` 4 or 5) — solid green border.
5. Otherwise — plain default styling.

Priority is a 0–5 scale (0 = highest, 5 = lowest), shown as a colored dot
(red 0-1, yellow 2-3, green 4-5) plus the number on each card. Labels are
shown as colored chips. Stale Intangible tasks get an extra warning line.

Within a lane, tasks whose due date is approaching/overdue and are
Fecha-fija sort to the top; otherwise sorted by soonest due date, then
priority.

## Requirements

- Python 3.10+
- [Poetry](https://python-poetry.org/)

## Setup

```bash
poetry install
```

## Running

```bash
poetry run kanban-tui
```

By default tasks are stored in `~/KanbanTasks` (created on first run, with a
config file at `~/.config/kanban-tui/config.json`). To point at a different
folder — e.g. a MEGA-synced directory — either edit that config file's
`tasks_dir`, or set an env var for one run:

```bash
KANBAN_TUI_TASKS_DIR=~/MEGA/KanbanTasks poetry run kanban-tui
```

To try it immediately with the bundled sample tasks in this repo:

```bash
KANBAN_TUI_TASKS_DIR=./tasks poetry run kanban-tui
```

## Syncing across machines with MEGA

1. Install the MEGA desktop sync client and let it sync a folder, e.g.
   `~/MEGA/KanbanTasks`.
2. On every machine, set `tasks_dir` in `~/.config/kanban-tui/config.json`
   (or `KANBAN_TUI_TASKS_DIR`) to that synced folder.
3. The app polls the folder every few seconds and auto-reloads when files
   change, so edits made on another machine show up without restarting.
   Press `r` to force a manual reload at any time.

## Keybindings

| Key | Action |
|---|---|
| `←/h` `→/l` | Switch column within the active lane |
| `↑/k` `↓/j` | Move selection within a column |
| `shift+↑` / `K` | Switch to the previous lane |
| `shift+↓` / `J` | Switch to the next lane |
| `n` | New task (created in the active lane/column) |
| `enter` / `e` | Edit selected task |
| `d` | Delete selected task (asks to confirm) |
| `shift+←` / `H` | Move task to the previous column (checks WIP) |
| `shift+→` / `L` | Move task to the next column (checks WIP) |
| `c` | Close the active lane — always asks to confirm (not available for Urgencias) |
| `s` | Show the active lane's full summary (every task's Resumen + Criterio de aceptación) |
| `o` | Open the objectives screen (create / close / reopen / reprioritize lanes) |
| `m` | Show kanban metrics |
| `r` | Reload from disk |
| `q` | Quit |

Clicking a card also selects and opens it for editing.

### Inside the objectives screen (`o`)

| Key | Action |
|---|---|
| `↑` / `↓` | Select a row in the objectives list |
| `c` | Close the selected (active) objective — always asks to confirm |
| `r` | Reopen the selected (closed) objective |
| `+` / `-` | Raise / lower the selected objective's priority |
| `enter` (while typing a name) | Create the new objective |
| `escape` | Close the window |

## Building a deliverable

```bash
./build.sh
```

This installs dependencies, builds a wheel/sdist with Poetry
(`dist/kanban_tui-*.whl`), and — if PyInstaller is available — also produces
a standalone single-file dev binary at `dist/kanban-tui-dev` that can be
copied to another machine and run directly, without installing Python or
Poetry there.
