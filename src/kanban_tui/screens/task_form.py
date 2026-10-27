from __future__ import annotations

from datetime import date, datetime

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from ..models import PRIORITY_DEFAULT, ServiceClass, Status, Task
from ..settings import BoardSettings
from ..wip_rules import global_doing_count, intangible_state

STATUS_LABELS = {
    Status.BACKLOG: "Pendiente",
    Status.DOING: "En progreso",
    Status.DONE: "Hecho",
}

SERVICE_CLASS_LABELS = {
    ServiceClass.STANDARD: "Estándar",
    ServiceClass.FIXED_DATE: "Fecha fija",
    ServiceClass.EXPEDITE: "Expedito (urgente)",
    ServiceClass.INTANGIBLE: "Intangible",
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

    def __init__(
        self,
        task: Task | None = None,
        default_status: Status = Status.BACKLOG,
        objective_names: list[str] | None = None,
        default_objective: str = "",
        other_tasks: list[Task] | None = None,
        active_objective_names: list[str] | None = None,
        settings: BoardSettings | None = None,
    ) -> None:
        super().__init__()
        self.editing_task = task
        self.default_status = default_status
        self.objective_names = objective_names or []
        self.default_objective = default_objective
        self.other_tasks = other_tasks or []
        self.active_objective_names = active_objective_names or []
        self.settings = settings or BoardSettings()

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

                yield Label("Criterio de aceptación *")
                yield TextArea(task.acceptance_criteria if task else "", id="f-acceptance-criteria")

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
                        yield Label("Clase de servicio")
                        yield Select(
                            [(SERVICE_CLASS_LABELS[c], c) for c in ServiceClass],
                            value=task.service_class if task else ServiceClass.STANDARD,
                            id="f-service-class",
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
                        yield Label("Objetivo (no aplica a Expedito)")
                        current_objective = task.objective if task else self.default_objective
                        yield Select(
                            [(name, name) for name in self.objective_names],
                            value=current_objective if current_objective in self.objective_names else Select.NULL,
                            id="f-objective",
                            allow_blank=True,
                        )
                    with Vertical(classes="form-col"):
                        yield Label("Fecha límite (AAAA-MM-DD)")
                        yield Input(
                            value=task.due_date.isoformat() if task and task.due_date else "",
                            id="f-due-date",
                            placeholder=date.today().isoformat(),
                        )

                yield Label("Bloqueada por (mismo objetivo, opcional)")
                blocking_options = self._blocking_options(current_objective)
                blocking_ids = {option_id for _, option_id in blocking_options}
                yield Select(
                    blocking_options,
                    value=task.blocked_by if (task and task.blocked_by in blocking_ids) else Select.NULL,
                    id="f-blocked-by",
                    allow_blank=True,
                )

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

    def _blocking_options(self, objective_name: str) -> list[tuple[str, str]]:
        exclude_id = self.editing_task.id if self.editing_task else None
        return [
            (t.title, t.id)
            for t in self.other_tasks
            if t.objective == objective_name and t.id != exclude_id
        ]

    @on(Select.Changed, "#f-objective")
    def _on_objective_changed(self, event: "Select.Changed") -> None:
        value = event.value
        objective_name = "" if value == Select.NULL else value
        blocked_by_select = self.query_one("#f-blocked-by", Select)
        blocked_by_select.set_options(self._blocking_options(objective_name))

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

        acceptance_criteria = self.query_one("#f-acceptance-criteria", TextArea).text.strip()
        if not acceptance_criteria:
            error.update("[red]El criterio de aceptación es obligatorio[/red]")
            return

        status = self.query_one("#f-status", Select).value
        service_class = self.query_one("#f-service-class", Select).value
        priority = self.query_one("#f-priority", Select).value

        due_date: date | None = None
        if due_raw:
            try:
                due_date = date.fromisoformat(due_raw)
            except ValueError:
                error.update("[red]La fecha límite debe tener el formato AAAA-MM-DD[/red]")
                return
        elif service_class == ServiceClass.FIXED_DATE:
            error.update("[red]Las tareas de clase 'Fecha fija' necesitan una fecha límite[/red]")
            return
        objective_value = self.query_one("#f-objective", Select).value
        objective = "" if objective_value == Select.NULL else objective_value

        if service_class != ServiceClass.EXPEDITE and not objective:
            error.update("[red]Selecciona un objetivo (o crea uno primero con 'o')[/red]")
            return

        if service_class == ServiceClass.EXPEDITE:
            objective = ""

        blocked_by_value = self.query_one("#f-blocked-by", Select).value
        blocked_by = "" if blocked_by_value == Select.NULL else blocked_by_value

        if status == Status.DOING:
            if blocked_by:
                blocker = next((t for t in self.other_tasks if t.id == blocked_by), None)
                if blocker is not None and blocker.status != Status.DONE:
                    error.update(
                        f"[red]Bloqueada por «{blocker.title}». Termina esa tarea primero.[/red]"
                    )
                    return
            if service_class == ServiceClass.EXPEDITE:
                doing_count = sum(
                    1
                    for t in self.other_tasks
                    if t.service_class == ServiceClass.EXPEDITE and t.status == Status.DOING
                )
                if doing_count >= self.settings.expedite_doing_limit:
                    error.update(
                        f"[red]Ya hay {self.settings.expedite_doing_limit} tareas Expedito en progreso. "
                        "Termina alguna antes de empezar otra.[/red]"
                    )
                    return
            else:
                doing_count = global_doing_count(self.other_tasks, visible_names=self.objective_names)
                if doing_count >= self.settings.global_wip_limit:
                    error.update(
                        f"[red]Ya hay {self.settings.global_wip_limit} tarea(s) en progreso en el tablero "
                        "(límite de WIP global). Termina esa antes de empezar otra.[/red]"
                    )
                    return

                if service_class != ServiceClass.INTANGIBLE:
                    _, needs_intangible = intangible_state(
                        self.other_tasks, self.active_objective_names, self.settings.intangible_cadence
                    )
                    if objective in needs_intangible:
                        error.update(
                            f"[red]Toca hacer una tarea Intangible en «{objective}» antes de seguir "
                            "con Estándar/Fecha fija.[/red]"
                        )
                        return

        labels_raw = self.query_one("#f-labels", Input).value
        labels = [chunk.strip() for chunk in labels_raw.split(",") if chunk.strip()]
        description = self.query_one("#f-description", TextArea).text

        if self.editing_task:
            task = self.editing_task
            task.title = title
            task.description = description
            task.acceptance_criteria = acceptance_criteria
            task.status = status
            task.service_class = service_class
            task.priority = priority
            task.objective = objective
            task.labels = labels
            task.due_date = due_date
            task.blocked_by = blocked_by
            task.updated_at = datetime.now()
        else:
            task = Task(
                title=title,
                description=description,
                acceptance_criteria=acceptance_criteria,
                status=status,
                service_class=service_class,
                priority=priority,
                objective=objective,
                labels=labels,
                due_date=due_date,
                blocked_by=blocked_by,
            )

        if task.status == Status.DOING and task.started_at is None:
            task.started_at = date.today()
        elif task.status != Status.DOING and task.status != Status.DONE:
            task.started_at = None

        if task.status == Status.DONE and task.completed_at is None:
            task.completed_at = date.today()
        elif task.status != Status.DONE:
            task.completed_at = None

        self.dismiss(task)
