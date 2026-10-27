from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from .. import config
from ..settings import (
    BoardSettings,
    DEFAULT_APPROACHING_DAYS,
    DEFAULT_DUE_SOON_DAYS,
    DEFAULT_DUE_SOON_PRIORITY_CAP,
    DEFAULT_DUE_URGENT_DAYS,
    DEFAULT_DUE_URGENT_PRIORITY_CAP,
    DEFAULT_EXPEDITE_DOING_LIMIT,
    DEFAULT_GLOBAL_WIP_LIMIT,
    DEFAULT_INTANGIBLE_CADENCE,
    DEFAULT_MAX_ACTIVE_OBJECTIVES,
    DEFAULT_STALE_INTANGIBLE_DAYS,
    DEFAULT_STUCK_DOING_DAYS,
    load_settings,
    save_settings,
)

# input id -> BoardSettings field name, for every rule parameter in the panel.
_FIELD_MAP = {
    "set-global-wip": "global_wip_limit",
    "set-expedite-limit": "expedite_doing_limit",
    "set-max-objectives": "max_active_objectives",
    "set-intangible-cadence": "intangible_cadence",
    "set-stuck-days": "stuck_doing_days",
    "set-approaching-days": "approaching_days",
    "set-stale-days": "stale_intangible_days",
    "set-due-soon-days": "due_soon_days",
    "set-due-soon-cap": "due_soon_priority_cap",
    "set-due-urgent-days": "due_urgent_days",
    "set-due-urgent-cap": "due_urgent_priority_cap",
}


class SettingsScreen(ModalScreen[Path | None]):
    """Panel de configuración de la herramienta: carpeta de tareas y todos
    los parámetros configurables de las reglas (con valores por defecto
    sensatos ya puestos)."""

    def __init__(self, tasks_dir: Path) -> None:
        super().__init__()
        self.tasks_dir = tasks_dir
        self._settings = load_settings(tasks_dir)

    def compose(self) -> ComposeResult:
        s = self._settings
        with Vertical(id="settings-dialog"):
            yield Static("Ajustes de la herramienta", id="settings-title")
            with VerticalScroll(id="settings-body"):
                yield Static("Carpeta", classes="settings-section")
                yield Label("Carpeta de tareas")
                yield Input(value=str(self.tasks_dir), id="set-tasks-dir")
                yield Static(
                    "Al guardar, el tablero se recarga desde ahí (se crea si no existe). "
                    "No se borra ni se mueve nada de la carpeta anterior.",
                    classes="settings-hint",
                )

                yield Static("Límites de WIP y objetivos", classes="settings-section")
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label(f"WIP global (por defecto {DEFAULT_GLOBAL_WIP_LIMIT})")
                        yield Input(value=str(s.global_wip_limit), id="set-global-wip")
                    with Vertical(classes="form-col"):
                        yield Label(f"WIP de Urgencias (por defecto {DEFAULT_EXPEDITE_DOING_LIMIT})")
                        yield Input(value=str(s.expedite_doing_limit), id="set-expedite-limit")
                yield Label(f"Máximo de objetivos activos a la vez (por defecto {DEFAULT_MAX_ACTIVE_OBJECTIVES})")
                yield Input(value=str(s.max_active_objectives), id="set-max-objectives")

                yield Static("Cadencia e intangibles", classes="settings-section")
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label(f"Cadencia intangible: toca cada X (por defecto {DEFAULT_INTANGIBLE_CADENCE})")
                        yield Input(value=str(s.intangible_cadence), id="set-intangible-cadence")
                    with Vertical(classes="form-col"):
                        yield Label(f"Días en progreso antes de atascada (por defecto {DEFAULT_STUCK_DOING_DAYS})")
                        yield Input(value=str(s.stuck_doing_days), id="set-stuck-days")

                yield Static("Alertas por fecha", classes="settings-section")
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label(f"Días para marcar 'se acerca' (por defecto {DEFAULT_APPROACHING_DAYS})")
                        yield Input(value=str(s.approaching_days), id="set-approaching-days")
                    with Vertical(classes="form-col"):
                        yield Label(f"Días de abandono para Intangible 'a revisar' (por defecto {DEFAULT_STALE_INTANGIBLE_DAYS})")
                        yield Input(value=str(s.stale_intangible_days), id="set-stale-days")

                yield Static("Escalado automático de prioridad por fecha límite", classes="settings-section")
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label(f"Días para prioridad 'pronto' (por defecto {DEFAULT_DUE_SOON_DAYS})")
                        yield Input(value=str(s.due_soon_days), id="set-due-soon-days")
                    with Vertical(classes="form-col"):
                        yield Label(f"Prioridad tope 'pronto' 0-5 (por defecto {DEFAULT_DUE_SOON_PRIORITY_CAP})")
                        yield Input(value=str(s.due_soon_priority_cap), id="set-due-soon-cap")
                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label(f"Días para prioridad 'urgente' (por defecto {DEFAULT_DUE_URGENT_DAYS})")
                        yield Input(value=str(s.due_urgent_days), id="set-due-urgent-days")
                    with Vertical(classes="form-col"):
                        yield Label(f"Prioridad tope 'urgente' 0-5 (por defecto {DEFAULT_DUE_URGENT_PRIORITY_CAP})")
                        yield Input(value=str(s.due_urgent_priority_cap), id="set-due-urgent-cap")

                yield Static("", id="settings-error")
            with Horizontal(id="settings-actions"):
                yield Button("Cancelar", id="set-cancel", variant="default")
                yield Button("Guardar", id="set-save", variant="success")

    def on_mount(self) -> None:
        self.query_one("#set-tasks-dir", Input).focus()

    @on(Button.Pressed, "#set-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    @on(Button.Pressed, "#set-save")
    def save(self) -> None:
        error = self.query_one("#settings-error", Static)

        data: dict = {}
        for input_id, field_name in _FIELD_MAP.items():
            raw = self.query_one(f"#{input_id}", Input).value.strip()
            try:
                data[field_name] = int(raw)
            except ValueError:
                error.update(f"[red]«{field_name}» debe ser un número entero[/red]")
                return

        new_dir_raw = self.query_one("#set-tasks-dir", Input).value.strip()
        if not new_dir_raw:
            error.update("[red]La carpeta de tareas no puede quedar vacía[/red]")
            return
        new_dir = Path(new_dir_raw).expanduser()

        settings = BoardSettings.from_dict(data)

        if new_dir != self.tasks_dir:
            config.save_tasks_dir(new_dir)

        save_settings(new_dir, settings)
        self.dismiss(new_dir)
