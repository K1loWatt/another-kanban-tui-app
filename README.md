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

The objectives and settings popups are sized to fit all their fields on a
normal terminal without an inner scrollbar. The task form is the exception:
its Descripción and Criterio de aceptación fields are a full **10 lines**
each (there's real writing room to describe acceptance criteria properly),
so that form scrolls internally on anything but a tall terminal — by
design, not as a fallback.

The app's title bar shows the installed version (`Tablero Kanban v0.1.0`),
so you can always tell which build you're on at a glance.

Column titles (`PENDIENTES` / `EN PROGRESO` / `HECHO`) are printed once, in a
pinned header row at the top of the dashboard — they aren't repeated per
lane. A single horizontal rule separates one lane from the next (brighter
when that lane is the active one); task rows within a lane keep a consistent,
tight vertical rhythm with no extra spacing. Each lane's own title line
carries its per-column counts and, when relevant, its 💡 toca intangible /
⏸ apagado badges (e.g. `🎯 General · P3 · Pend 2 · Prog 1 · Hecho 4 · 💡 toca
intangible`). A banner right under the header shows the board's single
global WIP counter (e.g. `WIP global: 1/1`) — see [WIP limit](#wip-limit).
A paused objective's whole lane — title, description, every card — renders
in grey, regardless of any alert color it would otherwise have; it's still
fully editable, just visually out of the way.

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
[Objective summary](#objective-summary-s)), or press `v` on a single task to
see its full detail and comments without entering edit mode (see
[Task detail & comments](#task-detail--comments-v)).

## Swimlanes

The board is organized in horizontal **lanes**:

- **Urgencias** — a fixed lane at the top, always visible, that only ever
  shows tasks of the Expedite service class.
- One lane per **objective**, up to a configurable number of active
  objectives at a time (default 4, see [Settings](#settings-a)) (press
  `o` to manage them: create, pause/unpause, close, reopen, reprioritize —
  see [Keybindings](#keybindings)). Closing a lane archives its objective and
  hides it from the board entirely; its tasks stay on disk and are visible
  again if the objective is reopened.
- An objective can also be **paused** (apagado) instead of closed — press
  `p` on the board, or use the Apagar/Encender button in the objectives
  screen. A paused objective keeps its lane on the board (pushed to the
  bottom, below every active one, rendered all in grey) so you can still
  file, document and edit tasks against it, but it stops counting towards
  the active-objective cap and is exempt from the intangible-cadence rule
  below — it's parked, not gone.

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
  Urgencias lane's Backlog, but only a configurable number (default 2) can
  be in `Doing` at the same time — that cap is enforced only on the `Doing`
  column, same as any other lane's WIP.
- **Intangible** — important-but-not-urgent work; flagged on its card if it
  sits untouched for more than a configurable number of days (default 30),
  as a nudge to re-triage it.

## WIP limit

The board enforces a single **global WIP** (default 1) across every
objective lane combined — by default, only one Estándar/Fecha
fija/Intangible task can be `Doing` at a time, no matter which objective it
belongs to. It's shown as the `WIP global: n/limit` banner under the
header, turning red at the limit. The Urgencias lane is separate and keeps
its own WIP (default 2) in `Doing` (Expedito tasks can pile up freely in
Backlog — that limit only kicks in when moving one into `Doing`). Creating
or moving a task into Doing beyond either limit is blocked until another
one moves on. Both limits are configurable from the settings panel
(`a`, see [Settings](#settings-a)).

### Cadencia de intangibles

Within a single objective, every configurable **N** Estándar/Fecha fija
tasks finished in a row (default 3) you must finish an Intangible one
before starting another Estándar/Fecha fija task there — the lane shows
`💡 toca intangible` while that's pending. Starting an Intangible task is
always allowed and resets the counter. If the objective has **no**
Intangible task available to pick (none in Backlog or Doing), the rule is
skipped entirely — it never blocks you over work that doesn't exist yet.

The cadence is configurable from the settings panel (`a`, see
[Settings](#settings-a)), and is purely derived from each task's recorded
history (`status`/`service_class`/`objective`/`updated_at`) — there's no
separate state file to get out of sync, so editing/backdating task files by
hand changes the effective cadence state too.

### Blocked tasks

A task can be marked as **blocked by** another task in the same objective
(set from the task form's "Bloqueada por" field, which only lists siblings
of the currently selected objective). While its blocker isn't Hecho yet,
the blocked task renders in **red** on the board — title line tagged
`🔒 bloqueada`, and its Resumen line spells out which task is blocking it —
and it cannot be moved or created into `Doing` (same check in the quick
move shortcuts and in the form). Once the blocker is marked Hecho, the
block clears automatically; nothing needs to be unset by hand.

### Stuck-in-progress tasks

A task sitting in `Doing` for **N days or more** (default 5, configurable
from the settings panel — `a`) is flagged `⏳ atascada` and renders in
**purple**, as a nudge to either finish it or admit it's stuck and
split/requeue it. Press `f` on it to mark it Hecho and immediately open the
new-task popup to queue up what comes next in the same lane, in one motion.

## Due-date priority escalation

Every time the board loads or reloads (startup, pressing `r`, or picking up
an external file change), tasks with a due date and not yet Done get their
`priority` auto-raised the closer that date gets — it only ever makes a task
*more* important, never less, and leaves a task alone if you already gave it
a higher priority by hand. Both windows and both priority caps are
configurable from the settings panel (`a`):

- Due within **N days** (default 5, or already overdue by less than that):
  priority is capped at **C** (default 2) if it was lower priority (a
  higher number) than that.
- Due within **M days** (default 2), or overdue: priority is capped at
  **U** (default 0, the highest).

This is implemented in `storage.escalate_due_dates` and persists back to the
task's `.md` file, so the escalation is visible even outside the TUI.

## Metrics

Press `m` to open a read-only metrics screen: daily throughput (last 14
days — no weekly/sprint bucketing, this is a pull-based board), average lead
time and cycle time, the current global/Urgencias WIP, the intangible-cadence
streak of every active objective, counts of currently blocked and
stuck-in-progress tasks, and the distribution of active tasks by service
class.

## Objective summary (`s`)

Press `s` to open a read-only summary of the **active lane**: its stats
(Pendientes / En progreso / Hecho / Total), and every task in it with the
full, untruncated Resumen and Criterio de aceptación — the detail view for
the compact `|_` nodes shown on the board itself.

## Task detail & comments (`v`)

Press `v` on the selected task to open a read-only detail view — full
Resumen, Criterio de aceptación, and its comment thread — without entering
the edit form. It also has a small input to append a new comment on the
spot; comments are timestamped and saved straight into the task's own `.md`
file (under a `## Comentarios` section), so they sync with the rest of the
task and need no separate storage.

## Settings (`a`)

Press `a` to open the settings panel — every configurable parameter in the
app lives here, pre-filled with sensible defaults:

- **Carpeta de tareas** — the `tasks_dir` the board reads from. Saving a
  different path persists it to `~/.config/kanban-tui/config.json` (so it
  sticks across restarts, unless overridden by `KANBAN_TUI_TASKS_DIR`) and
  reloads the board from the new location right away, creating it if it
  doesn't exist yet. Nothing in the previous folder is touched, moved, or
  deleted.
- **WIP global** — the limit from [WIP limit](#wip-limit) (default 1).
- **WIP de Urgencias** — the Expedito `Doing` cap (default 2).
- **Máximo de objetivos activos a la vez** — the cap from
  [Swimlanes](#swimlanes) (default 4).
- **Cadencia intangible** — the N from [Cadencia de
  intangibles](#cadencia-de-intangibles) (default 3).
- **Días en progreso antes de marcar atascada** — the threshold from
  [Stuck-in-progress tasks](#stuck-in-progress-tasks) (default 5).
- **Días para marcar 'se acerca'** — the due-date window from
  [Alerts & board styling](#alerts--board-styling) (default 3).
- **Días de abandono para Intangible 'a revisar'** — the staleness nudge
  (default 30).
- **Escalado automático de prioridad por fecha límite** — the four knobs
  behind [Due-date priority escalation](#due-date-priority-escalation):
  days/priority-cap for "pronto" (default 5 days → priority 2) and for
  "urgente" (default 2 days → priority 0, the highest).

Every rule parameter is stored per tasks-folder, in that folder's own
`settings.json` — switching `tasks_dir` switches to that folder's own set
of rule parameters too. Saving always reloads the board immediately so new
limits (e.g. a different Urgencias WIP) take effect without restarting.

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
blocked_by: ""              # id of another task in the same objective, or empty
created_at: 2026-10-08 09:15:00
updated_at: 2026-10-09 08:00:00
---

Free-form description goes here (the Resumen shown on the board).

## Criterio de aceptación

The acceptance criteria goes here. Mandatory in the UI — the form won't
save a task without it.

## Comentarios

- 2026-10-27 09:15 — First comment, added from the task detail view (`v`).
- 2026-10-27 09:20 — Second comment; a multi-line one continues on the next
  lines, indented two spaces.
```

The body after the frontmatter holds the free-form description, then —
after the `## Criterio de aceptación` marker line — the acceptance
criteria, then — after `## Comentarios` — one `- YYYY-MM-DD HH:MM — text`
line per comment (continuation lines of a multi-line comment are indented).
The form requires acceptance criteria for every task (new or edited); older
files without it just show "(sin criterio de aceptación)" on the board
until you fill it in. Comments are optional and only added via the task
detail view (`v`), never required.

Older files with a legacy `type: normal|deadline|urgent` field are migrated
transparently on read (`normal`→Estándar, `deadline`→Fecha fija,
`urgent`→Expedito) and rewritten in the new format the next time they're
saved.

## Alerts & board styling

Each card shows one alert state (checked in this order, only one applies):

1. **Blocked** by another unfinished task in the same objective — solid
   red border, bold.
2. **Expedito** — blinks slowly in **red**.
3. **Stuck in progress** (`Doing` for N+ days, default 5) — solid **purple**
   border.
4. **Approaching due date** — due within N days (default 3) and not done —
   blinks slowly in **yellow**.
5. **Overdue** — due date in the past and not done — solid red border (no
   blink).
6. **Low priority** (`priority` 4 or 5) — solid green border.
7. Otherwise — plain default styling.

A paused objective's lane overrides all of the above to plain grey (see
[Swimlanes](#swimlanes)) — the alert state is still computed and still
affects move/create rules, it just isn't painted in color while parked.

Priority is a 0–5 scale (0 = highest, 5 = lowest), shown as a colored dot
(red 0-1, yellow 2-3, green 4-5) plus the number on each card. Labels are
shown as colored chips. Stale Intangible tasks get an extra warning line.

Within a lane, tasks whose due date is approaching/overdue and are
Fecha-fija sort to the top; otherwise sorted by soonest due date, then
priority.

## Installing a prebuilt binary (no Python needed)

```bash
curl -fsSL https://raw.githubusercontent.com/K1loWatt/another-kanban-tui-app/main/scripts/install.sh | bash
```

Downloads the latest GitHub release's Linux x86_64 binary and drops it at
`~/.local/bin/kanban-tui` (override with `KANBAN_TUI_INSTALL_DIR`). Re-run
the same command any time to **update** — it only ever replaces that one
binary; your tasks (`~/KanbanTasks`) and config
(`~/.config/kanban-tui/config.json`) live elsewhere and are never touched,
so nothing is lost across updates. If `~/.local/bin` isn't already on your
`PATH`, the script tells you the one line to add to your shell rc file.
Check what's installed any time with `kanban-tui --version`.

A new release is published automatically by
[`.github/workflows/release.yml`](.github/workflows/release.yml) whenever a
`v*` tag is pushed (e.g. `git tag v0.1.0 && git push origin v0.1.0`) — it
builds the binary with PyInstaller and attaches it to a GitHub Release.

## Requirements (running from source)

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
| `v` | View the selected task's full detail + comments (read-only) and add a comment |
| `f` | Mark the selected task Hecho and immediately open the popup to create the next backlog task in the same lane |
| `d` | Delete selected task (asks to confirm) |
| `shift+←` / `H` | Move task to the previous column (checks WIP/bloqueo/intangible) |
| `shift+→` / `L` | Move task to the next column (checks WIP/bloqueo/intangible) |
| `c` | Close the active lane — always asks to confirm (not available for Urgencias) |
| `p` | Pause/unpause the active lane's objective (not available for Urgencias) |
| `s` | Show the active lane's full summary (every task's Resumen + Criterio de aceptación) |
| `o` | Open the objectives screen (create / pause / unpause / close / reopen / reprioritize lanes) |
| `a` | Open the settings panel (tasks folder path + rule parameters) |
| `m` | Show kanban metrics |
| `r` | Reload from disk |
| `q` | Quit |

Clicking a card also selects and opens it for editing.

### Inside the objectives screen (`o`)

| Key | Action |
|---|---|
| `↑` / `↓` | Select a row in the objectives list |
| `c` | Close the selected objective (active or paused) — always asks to confirm |
| `r` | Reopen the selected (closed) objective |
| `p` | Pause the selected active objective, or unpause the selected paused one |
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
