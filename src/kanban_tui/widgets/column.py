from __future__ import annotations

from datetime import date

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ..models import ServiceClass, Status, Task
from ..settings import BoardSettings
from .task_card import TaskCard, compute_alert

STATUS_TITLES = {
    Status.BACKLOG: "PENDIENTES",
    Status.DOING: "EN PROGRESO",
    Status.DONE: "HECHO",
}

PAGE_SIZE = 5


class Column(Vertical):
    """Una columna del tablero (Pendientes / En progreso / Hecho) dentro de un carril.

    Sin scroll: muestra como mucho `PAGE_SIZE` tareas por página. Las
    ranuras de tarjeta se crean una sola vez y solo se repintan; moverse
    más allá de la última tarea de la página pasa a la siguiente.
    """

    def __init__(self, status: Status, lane_key: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.status = status
        self.lane_key = lane_key
        self.tasks: list[Task] = []
        self.id_to_task: dict[str, Task] = {}
        self.settings = BoardSettings()
        self.selected_index = 0
        self.is_active = False
        self._cards: list[TaskCard] = []
        self._hint: Static | None = None
        self._pager: Static | None = None
        self.add_class(f"column-{status.value}")

    def compose(self) -> ComposeResult:
        self._cards = [TaskCard() for _ in range(PAGE_SIZE)]
        for card in self._cards:
            card.display = False
            yield card
        self._hint = Static("Sin tareas", classes="empty-hint")
        yield self._hint
        self._pager = Static("", classes="column-pager")
        yield self._pager

    # ── datos ────────────────────────────────────────────────────────────

    def _blocking_task(self, task: Task) -> Task | None:
        if not task.blocked_by:
            return None
        blocker = self.id_to_task.get(task.blocked_by)
        if blocker is None or blocker.status == Status.DONE:
            return None
        return blocker

    def _sort_key(self, task: Task):
        fixed_date_urgent = task.service_class == ServiceClass.FIXED_DATE and (
            task.is_approaching(self.settings.approaching_days) or task.is_overdue
        )
        return (
            0 if fixed_date_urgent else 1,
            task.due_date or date.max,
            task.priority,
            task.title.lower(),
        )

    def set_tasks(
        self,
        tasks: list[Task],
        id_to_task: dict[str, Task] | None = None,
        settings: BoardSettings | None = None,
    ) -> None:
        """Solo guarda los datos; el repintado lo pide el carril (`render_page`)
        y únicamente cuando es el carril visible."""
        self.id_to_task = id_to_task or {}
        self.settings = settings or BoardSettings()
        self.tasks = sorted(tasks, key=self._sort_key)
        if self.tasks:
            self.selected_index = max(0, min(self.selected_index, len(self.tasks) - 1))
        else:
            self.selected_index = 0

    @property
    def page(self) -> int:
        return self.selected_index // PAGE_SIZE

    @property
    def page_count(self) -> int:
        return max(1, -(-len(self.tasks) // PAGE_SIZE))

    # ── pintado ──────────────────────────────────────────────────────────

    def render_page(self) -> None:
        if not self._cards:
            return
        start = self.page * PAGE_SIZE
        page_tasks = self.tasks[start : start + PAGE_SIZE]
        for i, card in enumerate(self._cards):
            if i < len(page_tasks):
                task = page_tasks[i]
                card.show_task(task, compute_alert(task, self._blocking_task(task), self.settings))
            else:
                card.clear()
        self._hint.display = not self.tasks
        pages = self.page_count
        self._pager.display = pages > 1
        if pages > 1:
            self._pager.update(f"pág {self.page + 1}/{pages}  ·  {len(self.tasks)} tareas")
        self.refresh_selection()

    def refresh_selection(self) -> None:
        if not self._cards:
            return
        local = self.selected_index - self.page * PAGE_SIZE
        for i, card in enumerate(self._cards):
            card.selected = self.is_active and i == local and card.task_data is not None
        self._hint.set_class(self.is_active and not self.tasks, "selected")

    def set_active(self, value: bool) -> None:
        if value != self.is_active:
            self.is_active = value
            self.refresh_selection()

    # ── navegación ───────────────────────────────────────────────────────

    def _select(self, index: int) -> None:
        old_page = self.page
        self.selected_index = index
        if self.page != old_page:
            self.render_page()
        else:
            self.refresh_selection()

    def move_selection(self, delta: int) -> None:
        if not self.tasks:
            return
        self._select((self.selected_index + delta) % len(self.tasks))

    def change_page(self, delta: int) -> None:
        if not self.tasks:
            return
        target = self.page + delta
        if not (0 <= target < self.page_count):
            return
        self._select(min(target * PAGE_SIZE, len(self.tasks) - 1))

    def get_selected_task(self) -> Task | None:
        if self.tasks and 0 <= self.selected_index < len(self.tasks):
            return self.tasks[self.selected_index]
        return None
