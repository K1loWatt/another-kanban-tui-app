from __future__ import annotations

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..models import Status, Task
from ..widgets.task_card import SERVICE_CLASS_ICON

STATUS_LABELS = {
    Status.BACKLOG: "Pendiente",
    Status.DOING: "En progreso",
    Status.DONE: "Hecho",
}

_STATUS_ORDER = {Status.DOING: 0, Status.BACKLOG: 1, Status.DONE: 2}


class ObjectiveSummaryScreen(ModalScreen[None]):
    """Resumen de solo lectura del carril activo: estado, WIP y cada tarea con su detalle."""

    def __init__(
        self,
        title: str,
        *,
        is_urgency: bool,
        priority: int | None,
        wip_limit: int | None,
        tasks: list[Task],
    ) -> None:
        super().__init__()
        self.lane_title = title
        self.is_urgency = is_urgency
        self.priority = priority
        self.wip_limit = wip_limit
        self.tasks = tasks

    def compose(self) -> ComposeResult:
        icon = "\U0001f6a8" if self.is_urgency else "\U0001f3af"
        heading = f"{icon} {self.lane_title}"
        if not self.is_urgency:
            heading += f"  ·  prioridad P{self.priority}"
        with Vertical(id="summary-dialog"):
            yield Static(heading, id="summary-title")
            yield Static(self._stats_line(), id="summary-stats")
            yield VerticalScroll(id="summary-body")
            with Horizontal(id="summary-actions"):
                yield Button("Cerrar", id="summary-done", variant="default")

    def _stats_line(self) -> str:
        backlog = sum(1 for t in self.tasks if t.status == Status.BACKLOG)
        doing = sum(1 for t in self.tasks if t.status == Status.DOING)
        done = sum(1 for t in self.tasks if t.status == Status.DONE)
        doing_text = f"{doing}/{self.wip_limit}" if self.wip_limit is not None else str(doing)
        return f"Pendientes {backlog}  ·  En progreso {doing_text}  ·  Hecho {done}  ·  Total {len(self.tasks)}"

    def on_mount(self) -> None:
        body = self.query_one("#summary-body", VerticalScroll)
        if not self.tasks:
            body.mount(Static("Sin tareas en este carril.", classes="empty-hint"))
            return
        ordered = sorted(self.tasks, key=lambda t: (_STATUS_ORDER[t.status], t.priority, t.title.lower()))
        for task in ordered:
            body.mount(self._task_block(task))

    @staticmethod
    def _task_block(task: Task) -> Static:
        icon = SERVICE_CLASS_ICON[task.service_class]
        header = (
            f"{icon} [bold]{escape(task.title)}[/bold]   "
            f"[dim]{STATUS_LABELS[task.status]} · P{task.priority}"
            f"{'  ·  vence ' + task.due_date.isoformat() if task.due_date else ''}[/dim]"
        )
        description = escape(task.description) or "(sin resumen)"
        acceptance = escape(task.acceptance_criteria) or "(sin criterio de aceptación)"
        text = (
            f"{header}\n"
            f"   [dim]|_[/dim] Resumen: {description}\n"
            f"   [dim]|_[/dim] Criterio de aceptación: {acceptance}"
        )
        return Static(text, classes="summary-task")

    @on(Button.Pressed, "#summary-done")
    def done(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
