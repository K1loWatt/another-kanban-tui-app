from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path

SETTINGS_FILENAME = "settings.json"

PRIORITY_MIN = 0
PRIORITY_MAX = 5

DEFAULT_INTANGIBLE_CADENCE = 3
DEFAULT_STUCK_DOING_DAYS = 5
DEFAULT_GLOBAL_WIP_LIMIT = 1
DEFAULT_EXPEDITE_DOING_LIMIT = 2
DEFAULT_MAX_ACTIVE_OBJECTIVES = 4
DEFAULT_APPROACHING_DAYS = 3
DEFAULT_STALE_INTANGIBLE_DAYS = 30
DEFAULT_DUE_SOON_DAYS = 5
DEFAULT_DUE_SOON_PRIORITY_CAP = 2
DEFAULT_DUE_URGENT_DAYS = 2
DEFAULT_DUE_URGENT_PRIORITY_CAP = 0


def _clamp_priority(value: int) -> int:
    return max(PRIORITY_MIN, min(PRIORITY_MAX, value))


@dataclass
class BoardSettings:
    # Peaje de WIP y cadencia de trabajo
    global_wip_limit: int = DEFAULT_GLOBAL_WIP_LIMIT
    expedite_doing_limit: int = DEFAULT_EXPEDITE_DOING_LIMIT
    intangible_cadence: int = DEFAULT_INTANGIBLE_CADENCE
    stuck_doing_days: int = DEFAULT_STUCK_DOING_DAYS
    # Objetivos
    max_active_objectives: int = DEFAULT_MAX_ACTIVE_OBJECTIVES
    # Alertas / fechas
    approaching_days: int = DEFAULT_APPROACHING_DAYS
    stale_intangible_days: int = DEFAULT_STALE_INTANGIBLE_DAYS
    due_soon_days: int = DEFAULT_DUE_SOON_DAYS
    due_soon_priority_cap: int = DEFAULT_DUE_SOON_PRIORITY_CAP
    due_urgent_days: int = DEFAULT_DUE_URGENT_DAYS
    due_urgent_priority_cap: int = DEFAULT_DUE_URGENT_PRIORITY_CAP

    def to_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: dict) -> "BoardSettings":
        defaults = cls()
        kwargs = {}
        for f in fields(cls):
            raw = data.get(f.name, getattr(defaults, f.name))
            try:
                value = int(raw)
            except (TypeError, ValueError):
                value = getattr(defaults, f.name)
            if f.name in ("due_soon_priority_cap", "due_urgent_priority_cap"):
                value = _clamp_priority(value)
            else:
                value = max(0, value)
            kwargs[f.name] = value
        return cls(**kwargs)


def _path(tasks_dir: Path) -> Path:
    return tasks_dir / SETTINGS_FILENAME


def load_settings(tasks_dir: Path) -> BoardSettings:
    path = _path(tasks_dir)
    if not path.exists():
        return BoardSettings()
    try:
        return BoardSettings.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return BoardSettings()


def save_settings(tasks_dir: Path, settings: BoardSettings) -> None:
    _path(tasks_dir).write_text(
        json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
