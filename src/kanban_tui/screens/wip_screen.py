from __future__ import annotations

from pathlib import Path
from typing import Callable

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ..colors import label_color
from ..models import Task
from ..widgets.task_card import SERVICE_CLASS_NAME
from .task_detail_screen import TaskDetailScreen


class WipScreen(ModalScreen[bool]):
    """Todo el trabajo en curso en una sola lista, sin separar por objetivo.

    `d` abre el detalle (con comentarios) de la tarea seleccionada y `x` la
    marca como Hecho. Devuelve True si se añadió algún comentario (para que
    el tablero recargue desde el disco)."""

    BINDINGS = [
        Binding("up,k", "move(-1)", "Arriba", show=False),
        Binding("down,j", "move(1)", "Abajo", show=False),
        Binding("d", "details", "Detalle / comentar"),
        Binding("x,X", "mark_done", "Marcar hecha"),
        Binding("escape,f12", "close", "Cerrar"),
    ]

    def __init__(
        self,
        tasks: list[Task],
        tasks_dir: Path,
        on_done: Callable[[Task], None],
    ) -> None:
        super().__init__()
        self.tasks = sorted(tasks, key=lambda t: (t.priority, (t.objective or "").lower(), t.title.lower()))
        self.tasks_dir = tasks_dir
        self.on_done = on_done
        self.selected_index = 0
        self.comments_changed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="wip-dialog"):
            yield Static("", id="wip-title")
            yield Static(
                "↑/↓ seleccionar  ·  d detalle y comentarios  ·  x marcar como hecha  ·  esc / F12 cerrar",
                id="wip-hint",
            )
            yield VerticalScroll(id="wip-body")

    def on_mount(self) -> None:
        self._render_rows()

    @staticmethod
    def _row_markup(task: Task) -> str:
        bits = [
            f"[bold]{escape(task.title)}[/bold]",
            SERVICE_CLASS_NAME[task.service_class],
            f"objetivo: {escape(task.objective or '-')}",
        ]
        if task.labels:
            bits.append(" ".join(f"[{label_color(l)}]{escape(l)}[/]" for l in task.labels))
        return "   ".join(bits)

    def _render_rows(self) -> None:
        self.query_one("#wip-title", Static).update(f"Trabajo en curso  ·  {len(self.tasks)} tarea(s)")
        body = self.query_one("#wip-body", VerticalScroll)
        body.remove_children()
        if not self.tasks:
            body.mount(Static("No hay tareas en progreso.", classes="empty-hint"))
            return
        self.selected_index = max(0, min(self.selected_index, len(self.tasks) - 1))
        body.mount_all(Static(self._row_markup(t), classes="wip-row") for t in self.tasks)
        self.call_after_refresh(self._refresh_selection)

    def _refresh_selection(self) -> None:
        rows = list(self.query(".wip-row"))
        for i, row in enumerate(rows):
            row.set_class(i == self.selected_index, "selected")
        if rows:
            rows[self.selected_index].scroll_visible(animate=False)

    def _selected(self) -> Task | None:
        if self.tasks and 0 <= self.selected_index < len(self.tasks):
            return self.tasks[self.selected_index]
        return None

    def action_move(self, delta: int) -> None:
        if not self.tasks:
            return
        self.selected_index = (self.selected_index + delta) % len(self.tasks)
        self._refresh_selection()

    def action_details(self) -> None:
        task = self._selected()
        if task is None:
            return

        def handle(changed: bool) -> None:
            if changed:
                self.comments_changed = True

        self.app.push_screen(TaskDetailScreen(task, self.tasks_dir), handle)

    def action_mark_done(self) -> None:
        task = self._selected()
        if task is None:
            return
        self.on_done(task)
        self.tasks = [t for t in self.tasks if t.id != task.id]
        self.notify(f"«{task.title}» marcada como hecha")
        self._render_rows()

    def action_close(self) -> None:
        self.dismiss(self.comments_changed)
