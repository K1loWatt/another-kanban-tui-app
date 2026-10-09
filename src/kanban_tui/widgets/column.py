from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Static

from ..models import Status, Task, TaskType
from .task_card import TaskCard

STATUS_TITLES = {
    Status.BACKLOG: "PENDIENTES",
    Status.DOING: "EN PROGRESO",
    Status.DONE: "HECHO",
}


class Column(Vertical):
    """Una columna del tablero (Pendientes / En progreso / Hecho)."""

    is_active: reactive[bool] = reactive(False)

    def __init__(self, status: Status, **kwargs) -> None:
        super().__init__(**kwargs)
        self.status = status
        self.tasks: list[Task] = []
        self.selected_index = 0
        self.add_class(f"column-{status.value}")

    def compose(self) -> ComposeResult:
        yield Static(self._header_text(), classes="column-header", id=f"header-{self.status.value}")
        yield VerticalScroll(id=f"body-{self.status.value}", classes="column-body")

    def _header_text(self) -> str:
        return f"{STATUS_TITLES[self.status]}  ({len(self.tasks)})"

    @staticmethod
    def _sort_key(task: Task):
        return (
            0 if task.type == TaskType.URGENT else 1,
            task.due_date or date.max,
            task.priority,
            task.title.lower(),
        )

    def set_tasks(self, tasks: list[Task]) -> None:
        self.tasks = sorted(tasks, key=self._sort_key)
        body = self.query_one(VerticalScroll)
        body.remove_children()
        if self.tasks:
            for task in self.tasks:
                body.mount(TaskCard(task))
        else:
            body.mount(Static("  Sin tareas", classes="empty-hint"))

        if self.tasks:
            self.selected_index = max(0, min(self.selected_index, len(self.tasks) - 1))
        else:
            self.selected_index = 0

        self.query_one(f"#header-{self.status.value}", Static).update(self._header_text())
        self.refresh_selection()

    def move_selection(self, delta: int) -> None:
        if not self.tasks:
            return
        self.selected_index = (self.selected_index + delta) % len(self.tasks)
        self.refresh_selection()

    def refresh_selection(self) -> None:
        cards = list(self.query(TaskCard))
        for i, card in enumerate(cards):
            card.selected = self.is_active and i == self.selected_index
        if self.is_active and cards:
            cards[self.selected_index].scroll_visible()

    def watch_is_active(self, value: bool) -> None:
        self.set_class(value, "active-column")
        self.refresh_selection()

    def get_selected_task(self) -> Task | None:
        if self.tasks and 0 <= self.selected_index < len(self.tasks):
            return self.tasks[self.selected_index]
        return None
