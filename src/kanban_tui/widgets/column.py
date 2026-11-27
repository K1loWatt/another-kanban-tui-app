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

    Sin scroll y con altura fija: siempre ocupa `PAGE_SIZE` ranuras (estén
    llenas o no), así el carril no cambia de alto al paginar. La ventana
    visible avanza de `PAGE_SIZE` en `PAGE_SIZE` pero la última página
    siempre muestra las últimas `PAGE_SIZE` tareas (con 8 tareas: 1-5 y
    luego 4-8), de modo que nunca aparece una página medio vacía.
    """

    def __init__(self, status: Status, lane_key: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.status = status
        self.lane_key = lane_key
        self.tasks: list[Task] = []
        self.id_to_task: dict[str, Task] = {}
        self.settings = BoardSettings()
        self.selected_index = 0
        self.window_start = 0
        self.is_active = False
        self._cards: list[TaskCard] = []
        self._hint: Static | None = None
        self._pager: Static | None = None
        self.add_class(f"column-{status.value}")

    def compose(self) -> ComposeResult:
        self._cards = [TaskCard() for _ in range(PAGE_SIZE)]
        for card in self._cards:
            card.clear()
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
        self.window_start = self._clamp_start(self.window_start)
        self._ensure_visible()

    @property
    def _last_start(self) -> int:
        return max(0, len(self.tasks) - PAGE_SIZE)

    def _clamp_start(self, start: int) -> int:
        return max(0, min(start, self._last_start))

    def _ensure_visible(self) -> None:
        """Mueve la ventana (de página en página) hasta que la tarea
        seleccionada quede dentro."""
        while self.selected_index >= self.window_start + PAGE_SIZE:
            self.window_start = self._clamp_start(self.window_start + PAGE_SIZE)
        while self.selected_index < self.window_start:
            self.window_start = self._clamp_start(self.window_start - PAGE_SIZE)

    @property
    def page(self) -> int:
        if self.window_start >= self._last_start:
            return self.page_count - 1
        return self.window_start // PAGE_SIZE

    @property
    def page_count(self) -> int:
        return max(1, -(-len(self.tasks) // PAGE_SIZE))

    # ── pintado ──────────────────────────────────────────────────────────

    def render_page(self) -> None:
        if not self._cards:
            return
        start = self.window_start
        page_tasks = self.tasks[start : start + PAGE_SIZE]
        for i, card in enumerate(self._cards):
            if i < len(page_tasks):
                task = page_tasks[i]
                card.show_task(task, compute_alert(task, self._blocking_task(task), self.settings))
            else:
                card.clear()
        self._hint.display = not self.tasks
        # La línea del paginador siempre ocupa su fila (vacía si no hace
        # falta) para que la altura de la columna no cambie nunca.
        pages = self.page_count
        self._pager.update(
            f"pág {self.page + 1}/{pages}  ·  {len(self.tasks)} tareas" if pages > 1 else ""
        )
        self.refresh_selection()

    def refresh_selection(self) -> None:
        if not self._cards:
            return
        local = self.selected_index - self.window_start
        for i, card in enumerate(self._cards):
            card.selected = self.is_active and i == local and card.task_data is not None
        self._hint.set_class(self.is_active and not self.tasks, "selected")

    def set_active(self, value: bool) -> None:
        if value != self.is_active:
            self.is_active = value
            self.refresh_selection()

    # ── navegación ───────────────────────────────────────────────────────

    def _select(self, index: int, window_start: int | None = None) -> None:
        old_start = self.window_start
        self.selected_index = index
        if window_start is not None:
            self.window_start = self._clamp_start(window_start)
        self._ensure_visible()
        if self.window_start != old_start:
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
        start = self._clamp_start(self.window_start + delta * PAGE_SIZE)
        if start == self.window_start:
            return
        # Al avanzar, el cursor cae en la primera tarea nueva (con 8 tareas,
        # en la 6ª); al retroceder, en la primera de la ventana.
        if delta > 0:
            index = min(self.window_start + PAGE_SIZE, len(self.tasks) - 1)
        else:
            index = start
        self._select(index, window_start=start)

    def get_selected_task(self) -> Task | None:
        if self.tasks and 0 <= self.selected_index < len(self.tasks):
            return self.tasks[self.selected_index]
        return None
