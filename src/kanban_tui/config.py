from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "kanban-tui" / "config.json"
DEFAULT_TASKS_DIR = Path.home() / "KanbanTasks"


def get_tasks_dir() -> Path:
    """Resolve the tasks directory.

    Priority: KANBAN_TUI_TASKS_DIR env var > config.json > default (~/KanbanTasks).
    Point this at a folder synced by MEGA (or any sync tool) to share the board
    across machines.
    """
    env_value = os.environ.get("KANBAN_TUI_TASKS_DIR")
    if env_value:
        return Path(env_value).expanduser()

    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
            configured = data.get("tasks_dir")
            if configured:
                return Path(configured).expanduser()
        except Exception:
            pass
    else:
        _write_default_config()

    return DEFAULT_TASKS_DIR


def save_tasks_dir(path: Path) -> None:
    """Persist a new tasks_dir to config.json, keeping any other keys already there."""
    data: dict = {}
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text())
        except Exception:
            data = {}
    data["tasks_dir"] = str(path)
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(data, indent=2))


def _write_default_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(
            {
                "_comment": (
                    "Point tasks_dir to a folder synced by MEGA (or any sync "
                    "tool) to share your kanban tasks across machines."
                ),
                "tasks_dir": str(DEFAULT_TASKS_DIR),
            },
            indent=2,
        )
    )
