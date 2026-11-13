from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

logger = logging.getLogger(__name__)

RECURRING_FILENAME = "recurring.json"
DEFAULT_INTERVAL_DAYS = 7


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass
class RecurringTask:
    """Una tarea que se repite cada tanto (ej. "limpiar baño"), fuera del
    tablero de objetivos: solo importa cuándo se hizo por última vez."""

    name: str
    description: str = ""
    interval_days: int = DEFAULT_INTERVAL_DAYS
    last_done: date | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: date = field(default_factory=date.today)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "interval_days": self.interval_days,
            "last_done": self.last_done.isoformat() if self.last_done else None,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RecurringTask":
        try:
            interval_days = max(1, int(data.get("interval_days", DEFAULT_INTERVAL_DAYS)))
        except (TypeError, ValueError):
            interval_days = DEFAULT_INTERVAL_DAYS
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            name=str(data.get("name") or "Tarea recurrente"),
            description=str(data.get("description") or ""),
            interval_days=interval_days,
            last_done=_parse_date(data.get("last_done")),
            created_at=_parse_date(data.get("created_at")) or date.today(),
        )


def _path(tasks_dir: Path) -> Path:
    return tasks_dir / RECURRING_FILENAME


def load_recurring_tasks(tasks_dir: Path) -> list[RecurringTask]:
    path = _path(tasks_dir)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [RecurringTask.from_dict(item) for item in raw]
    except Exception:
        logger.exception("Failed to parse recurring tasks file: %s", path)
        return []


def save_recurring_tasks(tasks_dir: Path, tasks: list[RecurringTask]) -> None:
    path = _path(tasks_dir)
    path.write_text(
        json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_recurring_task(
    tasks_dir: Path,
    name: str,
    description: str = "",
    interval_days: int = DEFAULT_INTERVAL_DAYS,
) -> RecurringTask:
    tasks = load_recurring_tasks(tasks_dir)
    task = RecurringTask(
        name=name.strip(),
        description=description.strip(),
        interval_days=max(1, interval_days),
    )
    tasks.append(task)
    save_recurring_tasks(tasks_dir, tasks)
    return task


def mark_done(tasks_dir: Path, task_id: str, when: date | None = None) -> None:
    tasks = load_recurring_tasks(tasks_dir)
    for task in tasks:
        if task.id == task_id:
            task.last_done = when or date.today()
            break
    save_recurring_tasks(tasks_dir, tasks)


def remove_recurring_task(tasks_dir: Path, task_id: str) -> None:
    tasks = [t for t in load_recurring_tasks(tasks_dir) if t.id != task_id]
    save_recurring_tasks(tasks_dir, tasks)


def _item_score(task: RecurringTask, today: date) -> float:
    """1.0 el día que se hizo, decayendo lineal hasta 0.0 el día del
    vencimiento (su `interval_days`). Pasado ese día resta en vez de
    sumar, un día entero más por cada día de retraso (-1, -2, -3…), sin
    tope inferior a nivel de item — el piso en 0 se aplica al total."""
    reference = task.last_done or task.created_at
    days = (today - reference).days
    interval = max(1, task.interval_days)
    if days <= interval:
        return 1.0 - (days / interval)
    overdue_days = days - interval
    return -float(overdue_days)


def recurring_health(tasks: list[RecurringTask], today: date | None = None) -> float:
    """Salud agregada (0.0 .. 1.0) del panel Recarga, para el indicador
    "Recarga Energía" de la barra superior: 1.0 si todo está recién hecho,
    bajando a medida que se acerca o pasa el vencimiento de cada item. Sin
    items todavía, se considera plena (nada que deba hacerse)."""
    if not tasks:
        return 1.0
    today = today or date.today()
    average = sum(_item_score(t, today) for t in tasks) / len(tasks)
    return max(0.0, min(1.0, average))


# Degradado rojo -> amarillo -> verde para mostrar la salud de Recarga.
_LOW_RED = (255, 85, 85)  # #ff5555
_MID_YELLOW = (255, 184, 108)  # #ffb86c
_HIGH_GREEN = (80, 250, 123)  # #50fa7b


def health_color(health: float) -> str:
    health = max(0.0, min(1.0, health))
    if health >= 0.5:
        t = (health - 0.5) / 0.5
        c1, c2 = _MID_YELLOW, _HIGH_GREEN
    else:
        t = health / 0.5
        c1, c2 = _LOW_RED, _MID_YELLOW
    r = round(c1[0] + (c2[0] - c1[0]) * t)
    g = round(c1[1] + (c2[1] - c1[1]) * t)
    b = round(c1[2] + (c2[2] - c1[2]) * t)
    return f"#{r:02x}{g:02x}{b:02x}"
