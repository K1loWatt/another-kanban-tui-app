# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.2.0]

### Added

- **Recarga** (`shift+r`): a new panel, separate from the board, for
  tracking recurring chores (name, optional description, interval in
  days, "última vez" done). Stored in its own `recurring.json`,
  independent of tasks.
- **🔋 Recarga Energía**: reflects the aggregate state of everything
  tracked in Recarga as a bold percentage + short bar, colored on a
  red → yellow → green gradient. Each item contributes 1.0 the day it's
  done, decaying to 0.0 at its due date, then going negative and growing
  by a full point per extra day overdue; the percentage is the average
  across every item, floored at 0%. See [Recarga
  Energía](README.md#recarga-energ%C3%ADa).
- The old separate `WIP global` / `Intangibles pendientes` banner and the
  new Recarga Energía indicator are now one single **stats banner**,
  centered, on its own subtly-colored background band so it stands out
  from the rest of the dashboard without being loud. (It went through a
  vertical bar next to the board — read as a scrollbar — and a wide
  three-line banner — too big — before landing here as one merged,
  compact line.)
- Tasks can now carry an optional "Por qué"-style **archived** state: `d`
  archives instead of deleting (see Changed below).

### Changed

- **Removed the dedicated Urgencias lane.** Expedite tasks now belong to
  an objective lane like every other task; their own cross-board `Doing`
  WIP cap (default 2) is unchanged, just no longer tied to a single lane.
  Old Expedite tasks without an objective get migrated to the default one
  on next load, same as any other orphaned task.
- `d` now **archives** a task instead of deleting its file: the task
  disappears from the board/metrics/WIP counts but its `.md` file is never
  removed from disk (sets `archived: true` in its frontmatter instead).
- Every date shown or typed in the UI (cards, task form, task detail,
  summaries, Metrics) now uses the Spanish **dd/mm/aaaa** format. On-disk
  frontmatter dates stay ISO (`aaaa-mm-dd`) — display/input only.

## [1.1.0]

### Added

- Each column (Pendientes/En progreso/Hecho) now caps at ~10 tasks tall
  and scrolls internally beyond that, instead of growing without limit
  and pushing every other lane off-screen.
- Each lane now has a bit of bottom padding, so its content doesn't sit
  flush against the next lane's top border.
- Objective lanes' top border, plus a very faint matching tint across the
  whole lane, is now colored on a green → red gradient based on how
  overdue the lane is for finishing a task, scaled by its own priority
  (P0 expects a task done daily to stay green, doubling the expected
  cadence per priority level down to P5 at 32 days). See [Lane freshness
  color](README.md#lane-freshness-color). The active lane's border
  renders heavy instead of thin to stay distinguishable regardless of
  color. Urgencias is explicitly excluded (its border stays neutral).
- Objectives can now carry an optional **"Por qué"** field (the
  motivation behind them), set at creation time in the objectives
  screen (`o`).

### Changed

- Urgencias' border no longer turns red — it was the only lane colored
  by something other than the new freshness gradient, which was
  confusing next to it. It now stays neutral, same as before any of this
  coloring existed; only its border thickness still marks it active.

## [1.0.2]

### Fixed

- The `v1.0.1` release was still built on `ubuntu-latest` (the
  `ubuntu-22.04` pin below landed in the same commit that tagged `v1.0.1`,
  but that tag had already been pushed from an older commit) and still
  shipped a binary requiring `GLIBC_2.42`. This release actually contains
  the pinned workflow.

## [1.0.1]

### Fixed

- `scripts/install.sh` rewritten in POSIX `sh` (no more `[[ ]]`/bashisms),
  so it no longer errors out under `dash`/`ash`/busybox when invoked as
  `sh install.sh` instead of `bash install.sh`.
- Release binary build pinned to the `ubuntu-22.04` GitHub Actions runner
  instead of `ubuntu-latest`, so the published binary links against an
  older glibc (2.35) and runs on more target machines — glibc is
  backward- but not forward-compatible, and building on too new a distro
  produced a binary that failed with `GLIBC_2.42 not found` on older
  systems.

## [1.0.0]

### Added

- Dracula color theme applied across the whole app (board, popups,
  scrollbars, alert colors).
- `💡 Intangibles pendientes: n` counter in the top bar and in the Metrics
  screen — a purely informational tally across the whole board
  ((Estándar/Fecha fija/Expedito tasks already Hecho) minus (Intangible
  tasks already Hecho)), recomputed on every reload.
- `tab` / `shift+tab` to switch between lanes on the board, and to move
  between fields inside whichever popup is open (task form, objectives,
  settings, metrics, summary, task detail).
- `pageup` / `pagedown` to jump the selection 3 tasks at a time within a
  column (or scroll a popup's body, if one is open).
- Default tasks folder (`KanbanTasks`) now lives next to wherever the
  binary/script is actually running from, instead of a fixed path.
- `.github/workflows/release.yml` now has explicit `contents: write`
  permissions so it can publish GitHub Releases on a `v*` tag push.

### Changed

- Installed binary renamed from `kanban-tui` to `kanban`
  (`scripts/install.sh`, `~/.local/bin/kanban`).
- All popups (task form, objectives, settings, metrics, summary, task
  detail) now open almost full-screen (94% of the terminal) instead of a
  fixed, content-sized box.
- Lane switching moved from `shift+←/→` to `tab` / `shift+tab`;
  `shift+←/→` (`H`/`L`) keep their original job of moving a task between
  columns.

### Removed

- The Intangible-cadence rule that blocked moving/creating a
  Standard/Fecha-fija task into `Doing` until an Intangible task was done
  first, along with its `intangible_cadence` setting. Replaced by the
  informational debt counter above — nothing is blocked anymore.

## [0.1.0]

Initial version: markdown-backed Kanban board with swimlanes per objective,
an Urgencias lane, four service classes (Estándar, Fecha fija, Expedito,
Intangible), configurable global/Urgencias WIP limits, blocked-task and
stuck-in-progress detection, due-date priority escalation, a read-only
metrics screen, per-lane objective summaries, task detail/comments view,
a settings panel, and a PyInstaller-based standalone binary build.
