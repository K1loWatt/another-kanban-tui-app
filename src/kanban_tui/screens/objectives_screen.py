from __future__ import annotations

from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from .. import storage
from ..models import Status, oneline
from ..objectives import (
    PRIORITY_DEFAULT,
    Objective,
    TooManyActiveObjectives,
    add_objective,
    close_objective,
    load_objectives,
    pause_objective,
    reopen_objective,
    set_priority,
    unpause_objective,
)
from ..settings import load_settings
from .confirm import ConfirmScreen

PRIORITY_OPTIONS = [(f"P{i}", i) for i in range(6)]


class ObjectivesScreen(ModalScreen[bool]):
    """Gestión de objetivos (carriles): crear, cerrar, reabrir, priorizar."""

    def __init__(self, tasks_dir: Path) -> None:
        super().__init__()
        self.tasks_dir = tasks_dir
        self.changed = False
        self.rows: list[Objective] = []
        self.selected_index = 0
        self._rows_focused = False
        self._max_active = load_settings(tasks_dir).max_active_objectives

    def compose(self) -> ComposeResult:
        with Vertical(id="objectives-dialog"):
            yield Static(
                f"Objetivos (máx. {self._max_active} activos a la vez)", id="objectives-title"
            )
            yield Static(
                "↑/↓ seleccionar fila · c cerrar · r reabrir · p apagar/encender · "
                "+/- prioridad · enter en Añadir crea uno",
                id="objectives-hint",
            )
            yield VerticalScroll(id="objectives-body")
            with Horizontal(classes="form-row"):
                yield Input(placeholder="Nombre del nuevo objetivo", id="obj-new-name")
                yield Select(
                    PRIORITY_OPTIONS, value=PRIORITY_DEFAULT, id="obj-new-priority", allow_blank=False
                )
                yield Button("Añadir", id="obj-new-btn", variant="success")
            yield Input(placeholder="Descripción del objetivo *", id="obj-new-description")
            yield Static("", id="objectives-error")
            with Horizontal(id="objectives-actions"):
                yield Button("Cerrar ventana", id="obj-done", variant="default")

    async def on_mount(self) -> None:
        await self.refresh_rows()
        self.query_one("#obj-new-name", Input).focus()

    def _load_sorted(self) -> list[Objective]:
        status_rank = {"active": 0, "paused": 1, "closed": 2}
        return sorted(
            load_objectives(self.tasks_dir),
            key=lambda o: (status_rank.get(o.status, 2), o.priority, o.created_at),
        )

    async def refresh_rows(self) -> None:
        self.rows = self._load_sorted()
        if self.rows:
            self.selected_index = max(0, min(self.selected_index, len(self.rows) - 1))
        body = self.query_one("#objectives-body", VerticalScroll)
        await body.remove_children()
        if not self.rows:
            body.mount(Static("Sin objetivos todavía.", classes="empty-hint"))
            return
        for objective in self.rows:
            if objective.is_active:
                badge = "🟢 activo"
            elif objective.is_paused:
                badge = "⏸ apagado"
            else:
                badge = "⚪ cerrado"
            row = Vertical(classes="objective-row", id=f"obj-row-{objective.id}")
            body.mount(row)
            header_row = Horizontal(classes="objective-row-header")
            row.mount(header_row)
            header_row.mount(
                Static(
                    f"{objective.name}  ·  P{objective.priority}  ·  {badge}",
                    classes="objective-row-name",
                )
            )
            if objective.is_active:
                header_row.mount(
                    Button("Apagar", id=f"obj-pause-{objective.id}", classes="objective-row-btn")
                )
                header_row.mount(
                    Button(
                        "Cerrar",
                        id=f"obj-close-{objective.id}",
                        classes="objective-row-btn",
                        variant="warning",
                    )
                )
            elif objective.is_paused:
                header_row.mount(
                    Button("Encender", id=f"obj-unpause-{objective.id}", classes="objective-row-btn")
                )
                header_row.mount(
                    Button(
                        "Cerrar",
                        id=f"obj-close-{objective.id}",
                        classes="objective-row-btn",
                        variant="warning",
                    )
                )
            else:
                header_row.mount(
                    Button("Reabrir", id=f"obj-reopen-{objective.id}", classes="objective-row-btn")
                )
            description = oneline(objective.description) if objective.description else "(sin descripción)"
            row.mount(Static(f"   {description}", classes="objective-row-description"))
        self._highlight_selected(move_focus=self._rows_focused)

    def _highlight_selected(self, move_focus: bool = True) -> None:
        for i, objective in enumerate(self.rows):
            try:
                row = self.query_one(f"#obj-row-{objective.id}", Vertical)
            except NoMatches:
                continue
            row.set_class(i == self.selected_index, "selected-row")
        if not move_focus or not self.rows:
            return
        objective = self.rows[self.selected_index]
        if objective.is_active:
            button_id = f"#obj-pause-{objective.id}"
        elif objective.is_paused:
            button_id = f"#obj-unpause-{objective.id}"
        else:
            button_id = f"#obj-reopen-{objective.id}"
        try:
            self.query_one(button_id, Button).focus()
        except NoMatches:
            pass

    def _unfinished_count(self, objective_name: str) -> int:
        tasks = storage.load_all_tasks(self.tasks_dir)
        return sum(1 for t in tasks if t.objective == objective_name and t.status != Status.DONE)

    @on(Input.Submitted, "#obj-new-name")
    @on(Input.Submitted, "#obj-new-description")
    @on(Button.Pressed, "#obj-new-btn")
    async def add_new(self) -> None:
        error = self.query_one("#objectives-error", Static)
        name_input = self.query_one("#obj-new-name", Input)
        description_input = self.query_one("#obj-new-description", Input)
        name = name_input.value.strip()
        description = description_input.value.strip()
        if not name:
            error.update("[red]Escribe un nombre para el objetivo[/red]")
            return
        if not description:
            error.update("[red]Escribe una descripción para el objetivo[/red]")
            return
        priority = self.query_one("#obj-new-priority", Select).value
        try:
            add_objective(self.tasks_dir, name, description, priority=priority, max_active=self._max_active)
        except TooManyActiveObjectives as exc:
            error.update(f"[red]{exc}[/red]")
            return
        error.update("")
        name_input.value = ""
        description_input.value = ""
        self.changed = True
        await self.refresh_rows()

    @on(Button.Pressed, "#obj-done")
    def done(self) -> None:
        self.dismiss(self.changed)

    def _close_objective(self, objective: Objective) -> None:
        self._rows_focused = True
        unfinished = self._unfinished_count(objective.name)

        def finalize() -> None:
            close_objective(self.tasks_dir, objective.id)
            self.changed = True
            self.run_worker(self.refresh_rows(), exclusive=False)

        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                finalize()

        if unfinished:
            message = (
                f"Este objetivo tiene {unfinished} tarea(s) sin terminar. "
                "Si lo cierras, quedarán archivadas junto al objetivo y "
                "desaparecerán del tablero. ¿Cerrar igualmente?"
            )
        else:
            message = f"¿Cerrar el objetivo «{objective.name}»?"

        self.app.push_screen(
            ConfirmScreen(message, confirm_label="Cerrar carril"),
            handle_confirm,
        )

    async def _reopen_objective(self, objective: Objective) -> None:
        self._rows_focused = True
        error = self.query_one("#objectives-error", Static)
        try:
            reopen_objective(self.tasks_dir, objective.id, max_active=self._max_active)
        except TooManyActiveObjectives as exc:
            error.update(f"[red]{exc}[/red]")
            return
        error.update("")
        self.changed = True
        await self.refresh_rows()

    async def _pause_objective(self, objective: Objective) -> None:
        self._rows_focused = True
        pause_objective(self.tasks_dir, objective.id)
        self.changed = True
        await self.refresh_rows()

    async def _unpause_objective(self, objective: Objective) -> None:
        self._rows_focused = True
        error = self.query_one("#objectives-error", Static)
        try:
            unpause_objective(self.tasks_dir, objective.id, max_active=self._max_active)
        except TooManyActiveObjectives as exc:
            error.update(f"[red]{exc}[/red]")
            return
        error.update("")
        self.changed = True
        await self.refresh_rows()

    async def _adjust_priority(self, objective: Objective, delta: int) -> None:
        if not objective.is_active:
            return
        self._rows_focused = True
        set_priority(self.tasks_dir, objective.id, objective.priority + delta)
        self.changed = True
        await self.refresh_rows()

    @on(Button.Pressed)
    async def handle_row_button(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("obj-close-"):
            objective = next((o for o in self.rows if o.id == button_id.removeprefix("obj-close-")), None)
            if objective is not None:
                self._close_objective(objective)
        elif button_id.startswith("obj-reopen-"):
            objective = next((o for o in self.rows if o.id == button_id.removeprefix("obj-reopen-")), None)
            if objective is not None:
                await self._reopen_objective(objective)
        elif button_id.startswith("obj-pause-"):
            objective = next((o for o in self.rows if o.id == button_id.removeprefix("obj-pause-")), None)
            if objective is not None:
                await self._pause_objective(objective)
        elif button_id.startswith("obj-unpause-"):
            objective = next((o for o in self.rows if o.id == button_id.removeprefix("obj-unpause-")), None)
            if objective is not None:
                await self._unpause_objective(objective)

    async def on_key(self, event) -> None:
        key = event.key
        if key == "escape":
            self.dismiss(self.changed)
            return

        if key == "up":
            if self.rows:
                self._rows_focused = True
                self.selected_index = (self.selected_index - 1) % len(self.rows)
                self._highlight_selected()
                event.stop()
            return
        if key == "down":
            if self.rows:
                self._rows_focused = True
                self.selected_index = (self.selected_index + 1) % len(self.rows)
                self._highlight_selected()
                event.stop()
            return

        if not self.rows:
            return
        objective = self.rows[self.selected_index]

        if key == "c" and not objective.is_closed:
            event.stop()
            self._close_objective(objective)
        elif key == "r" and objective.is_closed:
            event.stop()
            await self._reopen_objective(objective)
        elif key == "p" and objective.is_active:
            event.stop()
            await self._pause_objective(objective)
        elif key == "p" and objective.is_paused:
            event.stop()
            await self._unpause_objective(objective)
        elif event.character == "+":
            event.stop()
            await self._adjust_priority(objective, -1)
        elif event.character == "-":
            event.stop()
            await self._adjust_priority(objective, 1)
