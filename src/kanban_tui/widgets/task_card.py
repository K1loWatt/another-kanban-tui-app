from __future__ import annotations

from rich.markup import escape
from textual.reactive import reactive
from textual.widgets import Static

from ..colors import label_color
from ..models import ServiceClass, Status, Task
from ..settings import BoardSettings

SERVICE_CLASS_NAME = {
    ServiceClass.EXPEDITE: "Expedito",
    ServiceClass.FIXED_DATE: "Fecha fija",
    ServiceClass.STANDARD: "Estándar",
    ServiceClass.INTANGIBLE: "Intangible",
}

LOW_PRIORITY_THRESHOLD = 4

_ALERT_CLASSES = (
    "alert-blocked",
    "alert-urgent",
    "alert-stuck",
    "alert-approaching",
    "alert-overdue",
    "alert-low",
    "alert-normal",
)


def compute_alert(task: Task, blocking_task: Task | None, settings: BoardSettings) -> str:
    if blocking_task is not None:
        return "blocked"
    if task.status != Status.DONE:
        if task.service_class == ServiceClass.EXPEDITE:
            return "urgent"
        if task.is_stuck_doing(settings.stuck_doing_days):
            return "stuck"
        if task.is_overdue:
            return "overdue"
        if task.is_approaching(settings.approaching_days):
            return "approaching"
    if task.priority >= LOW_PRIORITY_THRESHOLD:
        return "low"
    return "normal"


def card_markup(task: Task) -> str:
    """Una sola línea: título + tipo + etiquetas. Sin emojis."""
    bits = [
        f"[bold]{escape(task.title)}[/bold]",
        f"[$text-muted]{SERVICE_CLASS_NAME[task.service_class]}[/]",
    ]
    if task.labels:
        bits.append(" ".join(f"[{label_color(l)}]{escape(l)}[/]" for l in task.labels))
    return "  ".join(bits)


class TaskCard(Static):
    """Una ranura de tarjeta reutilizable: la columna crea un número fijo de
    ranuras una sola vez y solo cambia su contenido al paginar o recargar,
    en lugar de desmontar/montar widgets (que es lo que hacía lento el
    tablero)."""

    can_focus = False

    selected: reactive[bool] = reactive(False)

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.task_data: Task | None = None
        self._markup = ""
        self._alert = ""

    def show_task(self, task: Task, alert: str) -> None:
        self.task_data = task
        markup = card_markup(task)
        if markup != self._markup:
            self._markup = markup
            self.update(markup)
        if alert != self._alert:
            self.remove_class(*_ALERT_CLASSES)
            self.add_class(f"alert-{alert}")
            self._alert = alert
        self.display = True

    def clear(self) -> None:
        self.task_data = None
        self.selected = False
        self.display = False

    def watch_selected(self, value: bool) -> None:
        self.set_class(value, "selected")

    def on_click(self) -> None:
        if self.task_data is not None:
            self.app.select_card(self.task_data)
