from __future__ import annotations

from rich.markup import escape
from textual.reactive import reactive
from textual.widgets import Static

from ..colors import label_color, priority_color
from ..models import Status, Task, TaskType

TYPE_ICON = {
    TaskType.URGENT: "\U0001f525",
    TaskType.DEADLINE: "⏰",
    TaskType.NORMAL: "\U0001f4cb",
}

LOW_PRIORITY_THRESHOLD = 4


class TaskCard(Static):
    """Una tarjeta de tarea dentro de una columna del tablero."""

    can_focus = False

    selected: reactive[bool] = reactive(False)
    blink_on: reactive[bool] = reactive(False)

    def __init__(self, task: Task, **kwargs) -> None:
        self.task_data = task
        self.alert = self._compute_alert()
        super().__init__(self._build_markup(), **kwargs)
        self._apply_alert_class()

    def _compute_alert(self) -> str:
        task = self.task_data
        if task.status != Status.DONE:
            if task.type == TaskType.URGENT:
                return "urgent"
            if task.is_overdue:
                return "overdue"
            if task.is_approaching:
                return "approaching"
        if task.priority >= LOW_PRIORITY_THRESHOLD:
            return "low"
        return "normal"

    def _apply_alert_class(self) -> None:
        self.remove_class("alert-urgent", "alert-approaching", "alert-overdue", "alert-low", "alert-normal")
        self.add_class(f"alert-{self.alert}")

    def watch_selected(self, value: bool) -> None:
        self.set_class(value, "selected")

    def watch_blink_on(self, value: bool) -> None:
        self.set_class(value and self.alert in ("urgent", "approaching"), "blink-active")

    def _build_markup(self) -> str:
        task = self.task_data
        icon = TYPE_ICON[task.type]
        lines = [f"{icon} [bold]{escape(task.title)}[/bold]"]

        color = priority_color(task.priority)
        meta = f"[{color}]●[/] P{task.priority}"
        if task.due_date:
            due_style = "bold red" if task.is_overdue else "dim"
            etiqueta = "vencida" if task.is_overdue else "vence"
            meta += f"   [{due_style}]{etiqueta} {task.due_date.isoformat()}[/{due_style}]"
        lines.append(meta)

        if task.labels:
            chips = "  ".join(f"[{label_color(l)}]▐[/] {escape(l)}" for l in task.labels)
            lines.append(chips)

        return "\n".join(lines)

    def on_click(self) -> None:
        self.app.select_card(self.task_data)
