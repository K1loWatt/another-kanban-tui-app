from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from ..models import format_date, oneline
from ..recurring import (
    DEFAULT_INTERVAL_DAYS,
    RecurringTask,
    add_recurring_task,
    load_recurring_tasks,
    mark_done,
    remove_recurring_task,
)


class RecurringScreen(ModalScreen[bool]):
    """Recarga: tareas recurrentes (ej. "limpiar baño") con la fecha en que
    se hicieron por última vez y cada cuánto hay que repetirlas,
    actualizable desde el mismo panel. Alimenta la barra de salud lateral
    del tablero."""

    def __init__(self, tasks_dir: Path) -> None:
        super().__init__()
        self.tasks_dir = tasks_dir
        self.rows: list[RecurringTask] = []
        self.changed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="recurring-dialog"):
            yield Static("Recarga — tareas recurrentes", id="recurring-title")
            yield Static(
                "Tareas que repetís cada tanto, con la fecha en que las hiciste por "
                "última vez y el intervalo máximo entre una y otra. 'Hecho hoy' "
                "actualiza esa fecha. Alimentan la barra de salud del tablero.",
                id="recurring-hint",
            )
            yield VerticalScroll(id="recurring-body")
            with Horizontal(classes="form-row"):
                yield Input(placeholder="Nombre (ej. Limpiar baño)", id="rec-new-name")
                yield Input(
                    placeholder=f"Intervalo en días ({DEFAULT_INTERVAL_DAYS})",
                    id="rec-new-interval",
                )
                yield Button("Añadir", id="rec-new-btn", variant="success")
            yield Input(placeholder="Descripción (opcional)", id="rec-new-description")
            yield Static("", id="recurring-error")
            with Horizontal(id="recurring-actions"):
                yield Button("Cerrar ventana", id="rec-done", variant="default")

    async def on_mount(self) -> None:
        await self.refresh_rows()
        self.query_one("#rec-new-name", Input).focus()

    async def refresh_rows(self) -> None:
        self.rows = sorted(load_recurring_tasks(self.tasks_dir), key=lambda t: t.name.lower())
        body = self.query_one("#recurring-body", VerticalScroll)
        await body.remove_children()
        if not self.rows:
            body.mount(Static("Sin tareas recurrentes todavía.", classes="empty-hint"))
            return
        for task in self.rows:
            last = format_date(task.last_done) if task.last_done else "nunca"
            row = Vertical(classes="recurring-row", id=f"rec-row-{task.id}")
            body.mount(row)
            header_row = Horizontal(classes="recurring-row-header")
            row.mount(header_row)
            header_row.mount(
                Static(
                    f"{task.name}   ·   última vez: {last}   ·   cada {task.interval_days} día(s)",
                    classes="recurring-row-name",
                )
            )
            header_row.mount(
                Button("Hecho hoy", id=f"rec-done-{task.id}", classes="recurring-row-btn", variant="success")
            )
            header_row.mount(
                Button("Quitar", id=f"rec-remove-{task.id}", classes="recurring-row-btn", variant="warning")
            )
            if task.description:
                row.mount(Static(f"   {oneline(task.description)}", classes="recurring-row-description"))

    @on(Input.Submitted, "#rec-new-name")
    @on(Input.Submitted, "#rec-new-interval")
    @on(Input.Submitted, "#rec-new-description")
    @on(Button.Pressed, "#rec-new-btn")
    async def add_new(self) -> None:
        error = self.query_one("#recurring-error", Static)
        name_input = self.query_one("#rec-new-name", Input)
        interval_input = self.query_one("#rec-new-interval", Input)
        description_input = self.query_one("#rec-new-description", Input)
        name = name_input.value.strip()
        if not name:
            error.update("[red]Escribe un nombre[/red]")
            return
        interval_raw = interval_input.value.strip()
        interval_days = DEFAULT_INTERVAL_DAYS
        if interval_raw:
            try:
                interval_days = max(1, int(interval_raw))
            except ValueError:
                error.update("[red]El intervalo debe ser un número entero de días[/red]")
                return
        error.update("")
        add_recurring_task(self.tasks_dir, name, description_input.value.strip(), interval_days)
        name_input.value = ""
        interval_input.value = ""
        description_input.value = ""
        self.changed = True
        await self.refresh_rows()
        name_input.focus()

    @on(Button.Pressed)
    async def handle_row_button(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("rec-done-"):
            mark_done(self.tasks_dir, button_id.removeprefix("rec-done-"))
            self.changed = True
            await self.refresh_rows()
        elif button_id.startswith("rec-remove-"):
            remove_recurring_task(self.tasks_dir, button_id.removeprefix("rec-remove-"))
            self.changed = True
            await self.refresh_rows()
        elif button_id == "rec-done":
            self.dismiss(self.changed)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(self.changed)
