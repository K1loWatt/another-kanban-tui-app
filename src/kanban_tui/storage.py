from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

from .models import Status, Task

logger = logging.getLogger(__name__)

# Due-date priority escalation: the closer a task's due date, the more
# priority it auto-gains (lower number = higher priority). Never loosens an
# already-higher priority the user set by hand.
DUE_SOON_DAYS = 5
DUE_SOON_PRIORITY_CAP = 2
DUE_URGENT_DAYS = 2
DUE_URGENT_PRIORITY_CAP = 0


def ensure_tasks_dir(tasks_dir: Path) -> Path:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    return tasks_dir


def load_all_tasks(tasks_dir: Path) -> list[Task]:
    tasks: list[Task] = []
    for path in sorted(tasks_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
            tasks.append(Task.from_markdown(text, path=path))
        except Exception:
            logger.exception("Failed to parse task file: %s", path)
    return tasks


def load_active_tasks(tasks_dir: Path) -> list[Task]:
    """Igual que `load_all_tasks` pero sin las tareas archivadas — lo que
    usa el tablero y todos sus cálculos (WIP, métricas, bloqueos, etc).
    Una tarea archivada nunca se borra del disco, solo deja de contar."""
    return [t for t in load_all_tasks(tasks_dir) if not t.archived]


def save_task(tasks_dir: Path, task: Task) -> Task:
    if task.path is None:
        task.path = tasks_dir / task.filename()
    task.path.write_text(task.to_markdown(), encoding="utf-8")
    return task


def migrate_missing_objectives(tasks_dir: Path, tasks: list[Task], default_objective: str) -> None:
    """Assign the default objective to any pre-existing task that has none
    (including old Expedite tasks from before the dedicated Urgencias lane
    was removed — every task needs an objective/lane now)."""
    for task in tasks:
        if not task.objective:
            task.objective = default_objective
            save_task(tasks_dir, task)


def escalate_due_dates(
    tasks_dir: Path,
    tasks: list[Task],
    due_soon_days: int = DUE_SOON_DAYS,
    due_soon_cap: int = DUE_SOON_PRIORITY_CAP,
    due_urgent_days: int = DUE_URGENT_DAYS,
    due_urgent_cap: int = DUE_URGENT_PRIORITY_CAP,
) -> list[Task]:
    """Auto-raise priority as a task's due date approaches; runs on every reload.

    Within `due_urgent_days` of the deadline (or overdue): priority capped at
    `due_urgent_cap`. Within `due_soon_days`: capped at `due_soon_cap`. A task
    that is already more important than its cap (lower number) is left
    untouched — this only ever raises priority.
    """
    today = date.today()
    changed: list[Task] = []
    for task in tasks:
        if not task.due_date or task.status == Status.DONE:
            continue
        days_left = (task.due_date - today).days
        if days_left <= due_urgent_days:
            cap = due_urgent_cap
        elif days_left <= due_soon_days:
            cap = due_soon_cap
        else:
            continue
        if task.priority > cap:
            task.priority = cap
            task.updated_at = datetime.now()
            save_task(tasks_dir, task)
            changed.append(task)
    return changed


def archive_task(tasks_dir: Path, task: Task) -> None:
    """"Elimina" una tarea del tablero sin tocar el archivo: solo la marca
    como archivada. El .md se queda en disco para siempre; "d" ya no borra
    nada."""
    task.archived = True
    save_task(tasks_dir, task)


def unarchive_task(tasks_dir: Path, task: Task) -> None:
    task.archived = False
    save_task(tasks_dir, task)


def dir_signature(tasks_dir: Path) -> tuple:
    entries = []
    for path in sorted(tasks_dir.glob("*.md")):
        try:
            stat = path.stat()
            entries.append((path.name, stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            continue
    return tuple(entries)
