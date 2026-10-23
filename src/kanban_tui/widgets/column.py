from __future__ import annotations

from datetime import date

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import Static

from ..models import ServiceClass, Status, Task
from .task_card import TaskCard

STATUS_TITLES = {
    Status.BACKLOG: "PENDIENTES",
    Status.DOING: "EN PROGRESO",
    Status.DONE: "HECHO",
}


class Column(Vertical):
    """Una columna del tablero (Pendientes / En progreso / Hecho) dentro de un carril.

    Column titles only appear once, in the dashboard's pinned header row
    (see `#board-header` in app.py) — this widget renders just the task rows.
    """

    is_active: reactive[bool] = reactive(False)

    def __init__(self, status: Status, lane_key: str, wip_limit: int | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.status = status
        self.lane_key = lane_key
        self.wip_limit = wip_limit
        self.tasks: list[Task] = []
        self.selected_index = 0
        self.add_class(f"column-{status.value}")

    @staticmethod
    def _sort_key(task: Task):
        fixed_date_urgent = (
            task.service_class == ServiceClass.FIXED_DATE and (task.is_approaching or task.is_overdue)
        )
        return (
            0 if fixed_date_urgent else 1,
            task.due_date or date.max,
            task.priority,
            task.title.lower(),
        )

    def set_tasks(self, tasks: list[Task]) -> None:
        self.tasks = sorted(tasks, key=self._sort_key)
        self.remove_children()
        if self.tasks:
            for task in self.tasks:
                self.mount(TaskCard(task))
        else:
            self.mount(Static("  Sin tareas", classes="empty-hint"))

        if self.tasks:
            self.selected_index = max(0, min(self.selected_index, len(self.tasks) - 1))
        else:
            self.selected_index = 0

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
        self.refresh_selection()

    def get_selected_task(self) -> Task | None:
        if self.tasks and 0 <= self.selected_index < len(self.tasks):
            return self.tasks[self.selected_index]
        return None
