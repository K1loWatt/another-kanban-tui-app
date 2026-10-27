from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from re import sub as re_sub

logger = logging.getLogger(__name__)

OBJECTIVES_FILENAME = "objectives.json"
MAX_ACTIVE_OBJECTIVES = 4
DEFAULT_OBJECTIVE_NAME = "General"
EXPEDITE_DOING_LIMIT = 2
PRIORITY_MIN = 0
PRIORITY_MAX = 5
PRIORITY_DEFAULT = 3


def _clamp_priority(value: int) -> int:
    return max(PRIORITY_MIN, min(PRIORITY_MAX, value))


class TooManyActiveObjectives(Exception):
    pass


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re_sub(r"[^a-z0-9]+", "-", text)
    return re_sub(r"-{2,}", "-", text).strip("-") or "objetivo"


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass
class Objective:
    name: str
    description: str = ""
    status: str = "active"  # "active" | "paused" | "closed"
    priority: int = PRIORITY_DEFAULT  # 0 (highest) .. 5 (lowest)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: date = field(default_factory=date.today)
    closed_at: date | None = None

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    @property
    def is_paused(self) -> bool:
        return self.status == "paused"

    @property
    def is_closed(self) -> bool:
        return self.status == "closed"

    @property
    def is_visible(self) -> bool:
        """Objetivos activos o apagados siguen como carril en el tablero."""
        return self.status in ("active", "paused")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Objective":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            name=str(data.get("name") or "Objetivo"),
            description=str(data.get("description") or ""),
            status=str(data.get("status") or "active"),
            priority=_clamp_priority(int(data.get("priority", PRIORITY_DEFAULT))),
            created_at=_parse_date(data.get("created_at")) or date.today(),
            closed_at=_parse_date(data.get("closed_at")),
        )


def _path(tasks_dir: Path) -> Path:
    return tasks_dir / OBJECTIVES_FILENAME


def load_objectives(tasks_dir: Path) -> list[Objective]:
    path = _path(tasks_dir)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Objective.from_dict(item) for item in raw]
    except Exception:
        logger.exception("Failed to parse objectives file: %s", path)
        return []


def save_objectives(tasks_dir: Path, objectives: list[Objective]) -> None:
    path = _path(tasks_dir)
    path.write_text(
        json.dumps([o.to_dict() for o in objectives], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def active_objectives(objectives: list[Objective]) -> list[Objective]:
    return [o for o in objectives if o.is_active]


def paused_objectives(objectives: list[Objective]) -> list[Objective]:
    return [o for o in objectives if o.is_paused]


def visible_objectives(objectives: list[Objective]) -> list[Objective]:
    """Objetivos que siguen como carril en el tablero (activos + apagados)."""
    return [o for o in objectives if o.is_visible]


def ensure_default_objective(tasks_dir: Path) -> list[Objective]:
    """Create objectives.json with a starter objective if it doesn't exist yet."""
    if _path(tasks_dir).exists():
        return load_objectives(tasks_dir)
    objectives = [
        Objective(name=DEFAULT_OBJECTIVE_NAME, description="Objetivo general por defecto.")
    ]
    save_objectives(tasks_dir, objectives)
    return objectives


def add_objective(
    tasks_dir: Path,
    name: str,
    description: str,
    priority: int = PRIORITY_DEFAULT,
    max_active: int = MAX_ACTIVE_OBJECTIVES,
) -> Objective:
    objectives = load_objectives(tasks_dir)
    if len(active_objectives(objectives)) >= max_active:
        raise TooManyActiveObjectives(
            f"Ya hay {max_active} objetivos activos. Cierra uno antes de crear otro."
        )
    objective = Objective(
        name=name.strip(), description=description.strip(), priority=_clamp_priority(priority)
    )
    objectives.append(objective)
    save_objectives(tasks_dir, objectives)
    return objective


def set_priority(tasks_dir: Path, objective_id: str, priority: int) -> None:
    objectives = load_objectives(tasks_dir)
    for objective in objectives:
        if objective.id == objective_id:
            objective.priority = _clamp_priority(priority)
            break
    save_objectives(tasks_dir, objectives)


def close_objective(tasks_dir: Path, objective_id: str) -> None:
    objectives = load_objectives(tasks_dir)
    for objective in objectives:
        if objective.id == objective_id:
            objective.status = "closed"
            objective.closed_at = date.today()
            break
    save_objectives(tasks_dir, objectives)


def reopen_objective(
    tasks_dir: Path, objective_id: str, max_active: int = MAX_ACTIVE_OBJECTIVES
) -> None:
    objectives = load_objectives(tasks_dir)
    if len(active_objectives(objectives)) >= max_active:
        raise TooManyActiveObjectives(
            f"Ya hay {max_active} objetivos activos. Cierra uno antes de reabrir otro."
        )
    for objective in objectives:
        if objective.id == objective_id:
            objective.status = "active"
            objective.closed_at = None
            break
    save_objectives(tasks_dir, objectives)


def pause_objective(tasks_dir: Path, objective_id: str) -> None:
    """Apaga un objetivo activo: sigue como carril al final del tablero (se
    puede seguir documentando/creando/editando tareas en él) pero deja de
    contar para el máximo de objetivos activos ni para la cadencia de
    intangibles."""
    objectives = load_objectives(tasks_dir)
    for objective in objectives:
        if objective.id == objective_id and objective.is_active:
            objective.status = "paused"
            break
    save_objectives(tasks_dir, objectives)


def unpause_objective(
    tasks_dir: Path, objective_id: str, max_active: int = MAX_ACTIVE_OBJECTIVES
) -> None:
    objectives = load_objectives(tasks_dir)
    if len(active_objectives(objectives)) >= max_active:
        raise TooManyActiveObjectives(
            f"Ya hay {max_active} objetivos activos. Cierra o apaga uno antes de encender otro."
        )
    for objective in objectives:
        if objective.id == objective_id and objective.is_paused:
            objective.status = "active"
            break
    save_objectives(tasks_dir, objectives)
