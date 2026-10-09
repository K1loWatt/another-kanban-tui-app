from __future__ import annotations

import logging
from pathlib import Path

from .models import Task

logger = logging.getLogger(__name__)


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


def save_task(tasks_dir: Path, task: Task) -> Task:
    if task.path is None:
        task.path = tasks_dir / task.filename()
    task.path.write_text(task.to_markdown(), encoding="utf-8")
    return task


def delete_task(task: Task) -> None:
    if task.path and task.path.exists():
        task.path.unlink()


def dir_signature(tasks_dir: Path) -> tuple:
    entries = []
    for path in sorted(tasks_dir.glob("*.md")):
        try:
            stat = path.stat()
            entries.append((path.name, stat.st_mtime_ns, stat.st_size))
        except FileNotFoundError:
            continue
    return tuple(entries)
