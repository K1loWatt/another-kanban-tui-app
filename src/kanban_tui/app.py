from __future__ import annotations

from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widgets import Footer, Header

from . import storage
from .config import get_tasks_dir
from .models import Status, Task
from .screens.confirm import ConfirmScreen
from .screens.task_form import TaskFormScreen
from .widgets.column import Column
from .widgets.task_card import TaskCard

STATUS_ORDER = [Status.BACKLOG, Status.DOING, Status.DONE]


class KanbanApp(App):
    """A modern terminal kanban board backed by markdown files."""

    CSS_PATH = "kanban.tcss"
    TITLE = "Tablero Kanban"

    BINDINGS = [
        Binding("n", "new_task", "Nueva"),
        Binding("enter,e", "edit_task", "Editar"),
        Binding("d", "delete_task", "Eliminar"),
        Binding("left,h", "focus_left", "Columna", show=True),
        Binding("right,l", "focus_right", "Columna", show=False),
        Binding("up,k", "focus_up", "Arriba", show=False),
        Binding("down,j", "focus_down", "Abajo", show=False),
        Binding("shift+left,H", "move_left", "Mover ←"),
        Binding("shift+right,L", "move_right", "Mover →"),
        Binding("r", "reload", "Recargar"),
        Binding("q", "quit", "Salir"),
    ]

    def __init__(self, tasks_dir: Path | None = None) -> None:
        super().__init__()
        self.tasks_dir = tasks_dir or get_tasks_dir()
        self.active_column_index = 0
        self._last_signature: tuple = ()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="board"):
            for status in STATUS_ORDER:
                yield Column(status, id=f"column-{status.value}")
        yield Footer()

    def on_mount(self) -> None:
        storage.ensure_tasks_dir(self.tasks_dir)
        self.sub_title = str(self.tasks_dir)
        self.reload_tasks()
        self._refresh_active()
        self.set_interval(0.8, self._toggle_blink)
        self.set_interval(3.0, self._check_external_changes)

    @property
    def columns(self) -> list[Column]:
        return [self.query_one(f"#column-{s.value}", Column) for s in STATUS_ORDER]

    @property
    def active_column(self) -> Column:
        return self.columns[self.active_column_index]

    def reload_tasks(self, keep_selection: bool = False) -> None:
        selected_id = None
        if keep_selection:
            task = self.active_column.get_selected_task()
            selected_id = task.id if task else None

        tasks = storage.load_all_tasks(self.tasks_dir)
        by_status: dict[Status, list[Task]] = {s: [] for s in STATUS_ORDER}
        for task in tasks:
            by_status[task.status].append(task)

        for column in self.columns:
            column.set_tasks(by_status[column.status])

        if selected_id:
            self.select_task_by_id(selected_id)

        self._last_signature = storage.dir_signature(self.tasks_dir)
        self._refresh_active()

    def _refresh_active(self) -> None:
        for i, column in enumerate(self.columns):
            column.is_active = i == self.active_column_index

    def action_focus_left(self) -> None:
        self.active_column_index = max(0, self.active_column_index - 1)
        self._refresh_active()

    def action_focus_right(self) -> None:
        self.active_column_index = min(len(STATUS_ORDER) - 1, self.active_column_index + 1)
        self._refresh_active()

    def action_focus_up(self) -> None:
        self.active_column.move_selection(-1)

    def action_focus_down(self) -> None:
        self.active_column.move_selection(1)

    def action_new_task(self) -> None:
        status = self.active_column.status

        def handle(task: Task | None) -> None:
            if task is None:
                return
            storage.save_task(self.tasks_dir, task)
            self.reload_tasks()
            self.select_task_by_id(task.id)

        self.push_screen(TaskFormScreen(default_status=status), handle)

    def action_edit_task(self) -> None:
        task = self.active_column.get_selected_task()
        if task is not None:
            self.edit_task(task)

    def edit_task(self, task: Task) -> None:
        def handle(updated: Task | None) -> None:
            if updated is None:
                return
            storage.save_task(self.tasks_dir, updated)
            self.reload_tasks()
            self.select_task_by_id(updated.id)

        self.push_screen(TaskFormScreen(task=task), handle)

    def action_delete_task(self) -> None:
        task = self.active_column.get_selected_task()
        if task is None:
            return

        def handle(confirmed: bool) -> None:
            if confirmed:
                storage.delete_task(task)
                self.reload_tasks()

        self.push_screen(ConfirmScreen(f"¿Eliminar '{task.title}'?"), handle)

    def _move_active_task(self, delta: int) -> None:
        task = self.active_column.get_selected_task()
        if task is None:
            return
        idx = STATUS_ORDER.index(task.status)
        new_idx = idx + delta
        if not (0 <= new_idx < len(STATUS_ORDER)):
            return

        task.status = STATUS_ORDER[new_idx]
        if task.status == Status.DONE and task.completed_at is None:
            task.completed_at = date.today()
        elif task.status != Status.DONE:
            task.completed_at = None

        storage.save_task(self.tasks_dir, task)
        self.active_column_index = new_idx
        self.reload_tasks()
        self.select_task_by_id(task.id)

    def action_move_left(self) -> None:
        self._move_active_task(-1)

    def action_move_right(self) -> None:
        self._move_active_task(1)

    def action_reload(self) -> None:
        self.reload_tasks(keep_selection=True)
        self.notify("Recargado desde el disco")

    def select_task_by_id(self, task_id: str) -> None:
        for i, column in enumerate(self.columns):
            for j, task in enumerate(column.tasks):
                if task.id == task_id:
                    self.active_column_index = i
                    column.selected_index = j
                    self._refresh_active()
                    return

    def select_card(self, task: Task) -> None:
        self.select_task_by_id(task.id)
        self.edit_task(task)

    def _toggle_blink(self) -> None:
        if not self.is_running:
            return
        try:
            columns = self.columns
        except NoMatches:
            return
        for column in columns:
            for card in column.query(TaskCard):
                card.blink_on = not card.blink_on

    def _check_external_changes(self) -> None:
        if not self.is_running:
            return
        signature = storage.dir_signature(self.tasks_dir)
        if signature != self._last_signature:
            try:
                self.reload_tasks(keep_selection=True)
            except NoMatches:
                return


def run() -> None:
    KanbanApp().run()


if __name__ == "__main__":
    run()
