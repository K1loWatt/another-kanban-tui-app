# Kanban TUI

A modern terminal Kanban board (Python + [Textual](https://textual.textualize.io/))
where every task is a plain markdown file, so the board can be synced across
machines with MEGA (or Dropbox, Syncthing, git, etc.). The interface (labels,
dialogs, column headers) is in Spanish; this doc stays in English for
development notes.

## Look & feel

The board renders as one big minimalist table. Only the **active lane**
shows its tasks; every other lane collapses to its title line (with its
counts), so switching lanes is instant and the screen stays readable.

Each column (Pendientes/En progreso/Hecho) always takes the height of
**5** tasks, with no scrolling, so the lane never changes height while
you page. When a column has more, a `pág 1/2 · 8 tareas` line appears
under it: `↑`/`↓` flip to the next/previous page when you go past the edge,
and `pageup` / `pagedown` step one task at a time (stopping at the
first/last task). Every page is full: the last
one shows the last 5 tasks, overlapping the previous page if needed (with
8 tasks: 1–5, then 4–8). Columns are split by a vertical line.

Colors come entirely from **Textual themes**: the app has no colors of its
own, every border, alert and label uses the active theme's variables
(`$primary`, `$accent`, `$error`, `$warning`, `$success`, …). Pick a theme
with the command palette (`ctrl+p` → change theme). The default is the
app's own **`kanban-high-contrast`** theme — pure **black and white**, no
other color at all — defined in
[`src/kanban_tui/themes.py`](src/kanban_tui/themes.py) as a Textual `Theme`
and registered with `App.register_theme`, so it sits in the theme list
next to Textual's built-ins (textual-dark, nord, gruvbox, tokyo-night,
catppuccin, dracula, solarized, rose-pine, …). To add another theme, add a
`Theme` to `CUSTOM_THEMES` in that file. The choice is remembered per
machine in `~/.config/kanban-tui/config.json` (`"theme"`).

Every task card has a soft rounded border so neighbouring tasks are easy
to tell apart. The selected task gets a thick border in the theme's accent color (its left edge
keeps the alert color, if any); in an empty column the "Sin tareas" placeholder
gets that border instead, so the cursor never gets lost.

Every popup (task form, objectives, settings, metrics, summary, task detail)
opens almost full-screen (94% of the terminal) so there's room to work
without constant internal scrolling. `tab` / `shift+tab` move between
fields inside whichever popup is open — the same keys that switch lanes on
the board itself, repurposed for field navigation while a popup is active.
The task form's Descripción and Criterio de aceptación fields are a full
**10 lines** each (there's real writing room to describe acceptance
criteria properly).

The app's title bar shows the installed version (`Tablero Kanban v1.6.0`),
so you can always tell which build you're on at a glance. See
[CHANGELOG.md](CHANGELOG.md) for what changed in each version.

Column titles (`PENDIENTES` / `EN PROGRESO` / `HECHO`) are printed once, in a
pinned header row at the top of the dashboard — they aren't repeated per
lane. Two **continuous vertical lines** split the three columns from the
header row to the bottom of the board, crossing every lane, so the
separation never breaks between objectives. A horizontal rule separates
one lane from the next (the same for every lane; the active one is
already obvious because it's the only one expanded). Each lane's title row is
split into the same three cells: the name with its freshness meter,
priority and backlog count under Pendientes, `Prog N` under En progreso and
`Hecho N` under Hecho (e.g. `General ▕██████░░▏ 4 completadas · P3 · Pend 2 │
Prog 1 │ Hecho 4`). A paused lane shows `(apagado)` instead of the meter. Right under the
header, a single centered stats banner — on a subtly different background
so it stands out from the rest of the dashboard without being loud — rolls
up the board's three global indicators in one line: the global WIP counter
(e.g. `WIP global: 1/1`, see [WIP limit](#wip-limit)), the Intangibles
pendientes counter (a purely informational tally, not a limit, of how many
Intangible tasks you're "behind" on, computed as (Estándar/Fecha
fija/Expedito tasks already Hecho) minus (Intangible tasks already Hecho)
across the whole board), and Recarga Energía (see [Recarga
Energía](#recarga-energía)). A paused objective's whole lane — title, description, every card — renders
in grey, regardless of any alert color it would otherwise have; it's still
fully editable, just visually out of the way.

Each card is a single line: title, type and labels — no emojis anywhere in the UI —

```
Fix production outage on payments API   Expedito   bug
```

Press `d` on a task for its full detail (description, acceptance criteria,
due date, comments; see [Task detail & comments](#task-detail--comments-d)),
or `s` for the full text of every task in the active lane (see
[Objective summary](#objective-summary-s)).

## Swimlanes

The board is organized in horizontal **lanes**, one per **objective** — there's
no separate fixed lane for Expedite tasks anymore; every task, including
Expedite ones, belongs to an objective lane like any other:

- One lane per **objective**, up to a configurable number of active
  objectives at a time (default 4, see [Settings](#settings-a)) (press
  `o` to manage them: create, pause/unpause, close, reopen, reprioritize —
  see [Keybindings](#keybindings)). Closing a lane archives its objective and
  hides it from the board entirely; its tasks stay on disk and are visible
  again if the objective is reopened. An objective can also be **deleted**
  (`b` / `supr` or the Borrar button in the objectives window): it disappears
  from both the board and the objectives list, but nothing is removed from
  disk — its task `.md` files are untouched and its entry stays in
  `objectives.json` with `"status": "deleted"` (edit that back to `"active"`
  to recover it).
- An objective can also be **paused** (apagado) instead of closed — press
  `p` on the board, or use the Apagar/Encender button in the objectives
  screen. A paused objective keeps its lane on the board (pushed to the
  bottom, below every active one, rendered all in grey) so you can still
  file, document and edit tasks against it, but it stops counting towards
  the active-objective cap — it's parked, not gone.

Every objective requires a **description** when it's created (mandatory,
just like a task's acceptance criteria) and it's shown right on the
dashboard, as a muted line under the lane's title — no need to open the
objectives screen to remember what a lane is for. An objective can also
carry an optional **"Por qué"** (the motivation behind it) — set once at
creation time in the objectives screen (`o`); it's shown there under the
description but doesn't clutter the board itself.

Lanes are sorted by **objective priority** (0 = highest, shown first), then
by creation date. Objective priority is independent from each task's own
`priority` field.

### Lane freshness meter

Next to each objective's name there's a block meter followed by how many
tasks the lane has completed, `▕████████▏ 4 completadas`. The meter
that shows how overdue the lane is for finishing a task, scaled by its own
priority: higher-priority lanes need a task done more often to stay full.
Concretely, every priority level doubles the expected cadence versus the
one above it — P0 needs a task Hecho **daily** to stay full, P1 every 2
days, P2 every 4, P3 every 8, P4 every 16, P5 every 32 — and the meter
empties as the days since the lane's last completed task (or, if it has
none yet, since the objective was created) go from 0 to that cadence: full
is what used to be green, empty what used to be red. It's plain text, so
it reads the same in black and white or any theme. This is purely
visual — it doesn't block or gate anything, unlike the WIP limit. Paused
lanes show `(apagado)` instead.

Each lane has its own `Backlog` → `Doing` → `Done` columns. A task's column
is just a `status` field inside its markdown frontmatter — the file never
moves or gets renamed when you change columns, which keeps sync tools happy
(no move/rename conflicts).

## Service classes

Every task belongs to exactly one objective/lane — including Expedite ones,
which no longer get a dedicated lane — and has a service class:

- **Estándar** — default FIFO work, respects the lane's WIP limit strictly.
- **Fecha fija** — gains sort priority automatically as its due date gets
  close or passes.
- **Expedito** — true emergencies. Any number can sit queued in its lane's
  Backlog, but only a configurable number (default 2) can be in `Doing` at
  the same time across the *whole board*, regardless of which objective
  they belong to — that cap is enforced only on `Doing`.
- **Intangible** — important-but-not-urgent work; flagged on its card if it
  sits untouched for more than a configurable number of days (default 30),
  as a nudge to re-triage it.

## WIP limit

The board enforces a single **global WIP** (default 1) across every
objective lane combined — by default, only one Estándar/Fecha
fija/Intangible task can be `Doing` at a time, no matter which objective it
belongs to. It's shown as the `WIP global: n/limit` banner under the
header, turning red at the limit. Expedito tasks are exempt from that
global cap but have their own separate one (default 2) across the whole
board, wherever they happen to live (Expedito tasks can pile up freely in
Backlog — that limit only kicks in when moving one into `Doing`). Creating
or moving a task into Doing beyond either limit is blocked until another
one moves on. Both limits are configurable from the settings panel
(`a`, see [Settings](#settings-a)).

### Intangibles pendientes

There's no cadence rule or limit around Intangible tasks — any task can
move or be created into `Doing` regardless of how many Intangibles you've
done lately. Instead, the `Intangibles pendientes: n` counter in the top
bar is a purely informational tally across the whole board: (Estándar/Fecha
fija/Expedito tasks already Hecho) minus (Intangible tasks already Hecho).
It's recomputed on every reload directly from task history — nothing to
configure, and no separate state file to get out of sync.

### Blocked tasks

A task can be marked as **blocked by** another task in the same objective
(set from the task form's "Bloqueada por" field, which only lists siblings
of the currently selected objective). While its blocker isn't Hecho yet,
the blocked task renders with a **red** border on the board (open it with
`d` to see which task is blocking it) and it cannot be moved or created into `Doing` (same check in the quick
move shortcuts and in the form). Once the blocker is marked Hecho, the
block clears automatically; nothing needs to be unset by hand.

### Stuck-in-progress tasks

A task sitting in `Doing` for **N days or more** (default 5, configurable
from the settings panel — `a`) renders with a **purple** border, as a nudge to either finish it or admit it's stuck and
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
time and cycle time, the current global/Expedito WIP, the board-wide
Intangibles-pendientes debt, counts of currently blocked and
stuck-in-progress tasks, and the distribution of active tasks by service
class.

## Objective summary (`s`)

Press `s` to open a read-only summary of the **active lane**: its stats
(Pendientes / En progreso / Hecho / Total), and every task in it with the
full, untruncated Resumen and Criterio de aceptación — the detail view for
the compact `|_` nodes shown on the board itself.

## Task detail & comments (`d`)

Press `d` on the selected task to open a read-only detail view — full
Resumen, Criterio de aceptación, and its comment thread — without entering
the edit form. It also has a small input to append a new comment on the
spot; comments are timestamped and saved straight into the task's own `.md`
file (under a `## Comentarios` section), so they sync with the rest of the
task and need no separate storage.

## Trabajo en curso (`F12`)

`F12` opens a list of **every task In progress**, across all lanes, sorted
by the objective's priority first and then by the task's own priority. Each
row shows the title, its priority and objective on the left, and its type
and labels in a box at the right end. Inside it:

| Key | Action |
|---|---|
| `↑/k` `↓/j` | Select a task |
| `enter` / `d` | Open its detail view: full text, comments, and add a comment |
| `x` | Mark it Hecho (it leaves the list immediately) |
| `escape` / `F12` | Close the panel |

## Archiving tasks (`v`)

Press `v` on the selected task to archive it (asks to confirm first). An
archived task disappears from the board, from metrics, from WIP counts and
from every other lane calculation — but its `.md` file is **never deleted**
from disk, ever; archiving just sets an `archived: true` flag in its
frontmatter and leaves the file exactly where it was. There's currently no
in-app "unarchive" button — to bring one back, edit that flag out of the
file by hand (or delete the line) and reload (`r`).

## Recarga (`shift+r`)

Press `R` to open **Recarga**, a separate panel (not part of the board or
the objective lanes) for tracking recurring chores — the kind of task you
do over and over but that doesn't belong in a Backlog/Doing/Hecho flow,
like "limpiar baño". Each entry has a name, an optional description, an
**interval** in days (how long it can go before it's considered overdue),
and a "última vez" date; the **Hecho hoy** button stamps today's date on
it, and **Quitar** removes it from the list (also without ever touching a
task file — Recarga has its own separate `recurring.json` in the tasks
folder).

### Recarga Energía

The last segment of the stats banner described above — a **bold
percentage** followed by a short bar (e.g. `Recarga Energía — 62%
████████████░░░░░░░░░░░░`), both colored on a **red → yellow → green**
gradient — shows the aggregate health of everything tracked in Recarga.
For each
recurring item: its contribution is **1.0** (full) the day it was last
done, decaying in a straight line down to **0.0** on the day it's due
(`last_done + interval_days`); if it goes past due, the contribution turns
*negative* and keeps growing by one full point per extra day late (-1,
-2, -3…) — there's no floor on how negative a single item can get (every
recurring chore is treated as non-negotiable, so badly neglecting even one
of them is meant to tank the whole indicator). The percentage itself is
the **average** across every item, clamped so it never drops below 0%;
with nothing in Recarga yet, it shows 100% (nothing owed). It updates
every time the board reloads (`r`, any task action, or after closing
Recarga with a change).

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
- **WIP de Expedito** — the Expedito `Doing` cap (default 2).
- **Máximo de objetivos activos a la vez** — the cap from
  [Swimlanes](#swimlanes) (default 4).
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
limits (e.g. a different Expedito WIP) take effect without restarting.

## Task file format

Each task is one `.md` file with YAML frontmatter:

```markdown
---
id: a1b2c3d4
title: Fix production outage on payments API
status: doing             # backlog | doing | done
service_class: expedite   # standard | fixed_date | expedite | intangible
objective: "General"       # name of the objective/lane every task belongs to
priority: 0                # 0 (highest) .. 5 (lowest)
labels:
- bug
- backend
due_date: 2026-10-10        # optional; required only for fixed_date tasks
started_at:                 # set automatically the first time it enters Doing
completed_at:
blocked_by: ""              # id of another task in the same objective, or empty
archived: false              # true once archived with `v` — the file is never deleted
created_at: 2026-10-08 09:15:00
updated_at: 2026-10-09 08:00:00
---

Free-form description goes here (the Resumen shown on the board).

## Criterio de aceptación

The acceptance criteria goes here. Mandatory in the UI — the form won't
save a task without it.

## Comentarios

- 2026-10-27 09:15 — First comment, added from the task detail view (`d`).
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
detail view (`d`), never required.

Older files with a legacy `type: normal|deadline|urgent` field are migrated
transparently on read (`normal`→Estándar, `deadline`→Fecha fija,
`urgent`→Expedito) and rewritten in the new format the next time they're
saved.

### Date format

Every date shown or typed anywhere in the UI — task cards, the task form's
due-date field, task detail, objective/lane summaries, the daily-throughput
chart in Metrics — uses the Spanish **dd/mm/aaaa** format (e.g. `25/12/2026`),
including when typing a new due date into the form. This is a display/input
concern only: the on-disk `.md` frontmatter (`due_date`, `created_at`, etc.)
keeps the ISO `aaaa-mm-dd` format shown above, since that's what stays
sortable by filename/grep and keeps the files portable.

## Alerts & board styling

Each card shows one alert state (checked in this order, only one applies),
marked by the **shape of its left border** so it reads in black and white
(themes with color also tint it):

1. **Blocked** by another unfinished task in the same objective — double
   line `║`, bold (error color).
2. **Expedito** — full block `█` (error color).
3. **Stuck in progress** (`Doing` for N+ days, default 5) — dashed `╏`
   (secondary color).
4. **Approaching due date** — due within N days (default 3) and not done —
   heavy line `┃` (warning color).
5. **Overdue** — due date in the past and not done — half block `▌`
   (error color).
6. **Low priority** (`priority` 4 or 5) — ascii `|` (success color).
7. Otherwise — plain rounded border.

A paused objective's lane overrides all of the above to plain grey (see
[Swimlanes](#swimlanes)) — the alert state is still computed and still
affects move/create rules, it just isn't painted while parked.

Priority is a 0–5 scale (0 = highest, 5 = lowest); it isn't printed on
the card (see it with `d`). Labels are shown as colored chips.

Within a lane, tasks whose due date is approaching/overdue and are
Fecha-fija sort to the top; otherwise sorted by soonest due date, then
priority.

## Installing a prebuilt binary (no Python needed)

```bash
curl -fsSL https://raw.githubusercontent.com/K1loWatt/another-kanban-tui-app/main/scripts/install.sh | sh
```

Downloads the latest GitHub release's Linux x86_64 binary and drops it at
`~/.local/bin/kanban` (override with `KANBAN_TUI_INSTALL_DIR`). Re-run
the same command any time to **update** — it only ever replaces that one
binary; your tasks (`~/.local/bin/KanbanTasks` by default — a `KanbanTasks`
folder next to wherever the binary lives) and config
(`~/.config/kanban-tui/config.json`) are never touched, so nothing is lost
across updates. If `~/.local/bin` isn't already on your
`PATH`, the script tells you the one line to add to your shell rc file.
Check what's installed any time with `kanban --version`.

A new release is published automatically by
[`.github/workflows/release.yml`](.github/workflows/release.yml) whenever a
`v*` tag is pushed (e.g. `git tag v1.0.0 && git push origin v1.0.0`) — it
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

By default tasks are stored in a `KanbanTasks` folder created next to the
running binary/script (created on first run, with a config file at
`~/.config/kanban-tui/config.json`). To point at a different folder — e.g. a
MEGA-synced directory — either edit that config file's `tasks_dir`, or set an
env var for one run:

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
3. The app polls the folder every 5 seconds and auto-reloads when files
   change, so edits made on another machine show up without restarting.
   Press `r` to force a manual reload at any time.

## Keybindings

| Key | Action |
|---|---|
| `←/h` `→/l` | Switch column within the active lane |
| `↑/k` `↓/j` | Move selection within a column, one task at a time (flips page at the edge) |
| `pageup` / `pagedown` | Previous / next task in the active column, one at a time, stopping at the ends (scrolls a popup's body instead, if one is open) |
| `tab` | Switch to the next lane (moves focus to the next field instead, if a popup is open) |
| `shift+tab` | Switch to the previous lane (moves focus to the previous field instead, if a popup is open) |
| `n` | New task (created in the active lane/column) |
| `enter` / `e` | Edit selected task |
| `d` | View the selected task's full detail + comments (read-only) and add a comment |
| `f` | Mark the selected task Hecho and immediately open the popup to create the next backlog task in the same lane |
| `F12` | Open the Trabajo en curso panel (every In-progress task, all lanes) — see [Trabajo en curso](#trabajo-en-curso-f12) |
| `v` | Archive selected task (asks to confirm) — see [Archiving tasks](#archiving-tasks-v) |
| `,` | Move task back one column: Hecho → En progreso → Pendientes |
| `.` | Move task forward one column: Pendientes → En progreso → Hecho (checks WIP/bloqueo) |
| `c` | Close the active lane — always asks to confirm |
| `p` | Pause/unpause the active lane's objective |
| `s` | Show the active lane's full summary (every task's Resumen + Criterio de aceptación) |
| `o` | Open the objectives screen (create / pause / unpause / close / reopen / reprioritize lanes) |
| `R` (shift+r) | Open Recarga, the recurring-tasks panel — see [Recarga](#recarga-shiftr) |
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
| `b` / `supr` | Delete the selected objective (hidden everywhere, nothing removed from disk) — always asks to confirm |
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

## License

[MIT](LICENSE)
