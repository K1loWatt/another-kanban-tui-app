from __future__ import annotations

from datetime import date, datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from ..models import PRIORITY_DEFAULT, Status, Task, TaskType

STATUS_LABELS = {
    Status.BACKLOG: "Pendiente",
    Status.DOING: "En progreso",
    Status.DONE: "Hecho",
}

TYPE_LABELS = {
    TaskType.NORMAL: "Normal",
    TaskType.DEADLINE: "Con fecha límite",
    TaskType.URGENT: "Urgente",
}

PRIORITY_LABELS = {
    0: "0 · Más alta",
    1: "1",
    2: "2",
    3: "3 · Media",
    4: "4",
    5: "5 · Más baja",
}


class TaskFormScreen(ModalScreen[Task | None]):
    """Formulario para crear / editar una tarea."""

    def __init__(self, task: Task | None = None, default_status: Status = Status.BACKLOG) -> None:
        super().__init__()
        self.editing_task = task
        self.default_status = default_status

    def compose(self) -> ComposeResult:
        task = self.editing_task
        heading = "Editar tarea" if task else "Nueva tarea"
        with Vertical(id="form-dialog"):
            yield Static(heading, id="form-title")
            with VerticalScroll(id="form-body"):
                yield Label("Título")
                yield Input(value=task.title if task else "", id="f-title", placeholder="Título de la tarea")

                yield Label("Descripción")
                yield TextArea(task.description if task else "", id="f-description")

                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label("Estado")
                        yield Select(
                            [(STATUS_LABELS[s], s) for s in Status],
                            value=task.status if task else self.default_status,
                            id="f-status",
                            allow_blank=False,
                        )
                    with Vertical(classes="form-col"):
                        yield Label("Tipo")
                        yield Select(
                            [(TYPE_LABELS[t], t) for t in TaskType],
                            value=task.type if task else TaskType.NORMAL,
                            id="f-type",
                            allow_blank=False,
                        )
                    with Vertical(classes="form-col"):
                        yield Label("Prioridad")
                        yield Select(
                            [(PRIORITY_LABELS[i], i) for i in range(6)],
                            value=task.priority if task else PRIORITY_DEFAULT,
                            id="f-priority",
                            allow_blank=False,
                        )

                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-col"):
                        yield Label("Fecha límite (AAAA-MM-DD) *")
                        yield Input(
                            value=task.due_date.isoformat() if task and task.due_date else "",
                            id="f-due-date",
                            placeholder=date.today().isoformat(),
                        )
                    with Vertical(classes="form-col"):
                        yield Label("Etiquetas (separadas por comas)")
                        yield Input(
                            value=", ".join(task.labels) if task else "",
                            id="f-labels",
                            placeholder="bug, backend",
                        )

                yield Static("", id="form-error")

            with Horizontal(id="form-actions"):
                yield Button("Cancelar", id="f-cancel", variant="default")
                yield Button("Guardar", id="f-save", variant="success")

    def on_mount(self) -> None:
        self.query_one("#f-title", Input).focus()

    @on(Button.Pressed, "#f-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)

    @on(Button.Pressed, "#f-save")
    def save(self) -> None:
        error = self.query_one("#form-error", Static)
        title = self.query_one("#f-title", Input).value.strip()
        due_raw = self.query_one("#f-due-date", Input).value.strip()

        if not title:
            error.update("[red]El título es obligatorio[/red]")
            return

        if not due_raw:
            error.update("[red]La fecha límite es obligatoria[/red]")
            return

        try:
            due_date = date.fromisoformat(due_raw)
        except ValueError:
            error.update("[red]La fecha límite debe tener el formato AAAA-MM-DD[/red]")
            return

        labels_raw = self.query_one("#f-labels", Input).value
        labels = [chunk.strip() for chunk in labels_raw.split(",") if chunk.strip()]

        status = self.query_one("#f-status", Select).value
        task_type = self.query_one("#f-type", Select).value
        priority = self.query_one("#f-priority", Select).value
        description = self.query_one("#f-description", TextArea).text

        if self.editing_task:
            task = self.editing_task
            task.title = title
            task.description = description
            task.status = status
            task.type = task_type
            task.priority = priority
            task.labels = labels
            task.due_date = due_date
            task.updated_at = datetime.now()
        else:
            task = Task(
                title=title,
                description=description,
                status=status,
                type=task_type,
                priority=priority,
                labels=labels,
                due_date=due_date,
            )

        if task.status == Status.DONE and task.completed_at is None:
            task.completed_at = date.today()
        elif task.status != Status.DONE:
            task.completed_at = None

        self.dismiss(task)
