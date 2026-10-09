# Kanban TUI

A modern terminal Kanban board (Python + [Textual](https://textual.textualize.io/))
where every task is a plain markdown file, so the board can be synced across
machines with MEGA (or Dropbox, Syncthing, git, etc.). The interface (labels,
dialogs, column headers) is in Spanish; this doc stays in English for
development notes.

## Columns

`Backlog` → `Doing` → `Done`. A task's column is just a `status` field inside
its markdown frontmatter — the file never moves or gets renamed when you
change columns, which keeps sync tools happy (no move/rename conflicts).

## Task file format

Each task is one `.md` file with YAML frontmatter:

```markdown
---
id: a1b2c3d4
title: Fix production outage on payments API
status: doing        # backlog | doing | done
type: urgent          # normal | deadline | urgent
priority: 0            # 0 (highest) .. 5 (lowest)
labels:
- bug
- backend
due_date: 2026-10-10   # required completion/due date
completed_at:
created_at: 2026-10-08 09:15:00
updated_at: 2026-10-09 08:00:00
---

Free-form markdown description goes here.
```

## Alerts & board styling

Each card shows one alert state (checked in this order, only one applies):

1. **Urgent** (`type: urgent`) — blinks slowly in **red**.
2. **Approaching due date** — due within 3 days and not done — blinks slowly
   in **yellow**.
3. **Overdue** — due date in the past and not done — solid red border (no
   blink).
4. **Low priority** (`priority` 4 or 5) — solid green border.
5. Otherwise — plain default styling.

Priority is a 0–5 scale (0 = highest, 5 = lowest), shown as a colored dot
(red 0-1, yellow 2-3, green 4-5) plus the number on each card. Labels are
shown as colored chips.

The backlog (and every column) is always sorted: urgent tasks first, then by
soonest due date, then by priority.

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
| `←/h` `→/l` | Switch column |
| `↑/k` `↓/j` | Move selection within a column |
| `n` | New task (created in the active column) |
| `enter` / `e` | Edit selected task |
| `d` | Delete selected task (asks to confirm) |
| `shift+←` / `H` | Move task to the previous column |
| `shift+→` / `L` | Move task to the next column |
| `r` | Reload from disk |
| `q` | Quit |

Clicking a card also selects and opens it for editing.

## Building a deliverable

```bash
./build.sh
```

This installs dependencies, builds a wheel/sdist with Poetry
(`dist/kanban_tui-*.whl`), and — if PyInstaller is available — also produces
a standalone single-file dev binary at `dist/kanban-tui-dev` that can be
copied to another machine and run directly, without installing Python or
Poetry there.
