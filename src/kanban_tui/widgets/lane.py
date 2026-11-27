from __future__ import annotations

from datetime import date

from rich.markup import escape
from textual.app import ComposeResult
from textual.color import Color
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

from ..models import Status, Task, oneline
from ..settings import BoardSettings
from ..wip_rules import lane_freshness
from .column import Column

STATUS_ORDER = [Status.BACKLOG, Status.DOING, Status.DONE]

# Degradado verde -> rojo según qué tan "fresco" está el carril (ver lane_freshness).
_FRESH_GREEN = (80, 250, 123)  # #50fa7b
_STALE_RED = (255, 85, 85)  # #ff5555


def _gradient_color(ratio: float) -> str:
    r = round(_FRESH_GREEN[0] + (_STALE_RED[0] - _FRESH_GREEN[0]) * ratio)
    g = round(_FRESH_GREEN[1] + (_STALE_RED[1] - _FRESH_GREEN[1]) * ratio)
    b = round(_FRESH_GREEN[2] + (_STALE_RED[2] - _FRESH_GREEN[2]) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


class Lane(Vertical):
    """Un carril horizontal del tablero, uno por objetivo.

    Solo el carril activo despliega sus columnas y pinta tarjetas; los demás
    se quedan plegados en su línea de título (con los contadores), así
    cambiar de carril solo repinta dos carriles y no todo el tablero.
    """

    is_active: reactive[bool] = reactive(False)

    def __init__(
        self,
        lane_key: str,
        title: str,
        *,
        objective_id: str | None = None,
        priority: int | None = None,
        description: str = "",
        wip_limit: int | None = None,
        is_paused: bool = False,
        created_at: date | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.lane_key = lane_key
        self.title_text = title
        self.objective_id = objective_id
        self.priority = priority
        self.description = description
        self.wip_limit = wip_limit
        self.is_paused = is_paused
        self.created_at = created_at
        self.active_column_index = 0
        self.tasks: list[Task] = []
        self._columns: list[Column] = []
        self._title: Static | None = None
        self._body: Horizontal | None = None
        self._dirty = True
        self.add_class("objective-lane")
        if is_paused:
            self.add_class("paused-lane")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="lane-header"):
            self._title = Static(self._header_text(), classes="lane-title")
            yield self._title
        description = oneline(self.description) if self.description else "(sin descripción)"
        yield Static(f"   {description}", classes="lane-description")
        self._columns = [Column(status, lane_key=self.lane_key) for status in STATUS_ORDER]
        self._body = Horizontal(*self._columns, classes="lane-body")
        self._body.display = False
        yield self._body

    def _header_text(self) -> str:
        backlog = sum(1 for t in self.tasks if t.status == Status.BACKLOG)
        doing = sum(1 for t in self.tasks if t.status == Status.DOING)
        done = sum(1 for t in self.tasks if t.status == Status.DONE)

        if self.wip_limit is not None:
            doing_text = f"Prog {doing}/{self.wip_limit}"
            if doing >= self.wip_limit:
                doing_text = f"[bold #ff5f56]{doing_text}[/]"
        else:
            doing_text = f"Prog {doing}"

        badge_text = "   ·   [dim]⏸ apagado[/dim]" if self.is_paused else ""

        return (
            f"\U0001f3af [bold]{escape(self.title_text)}[/bold]   ·   P{self.priority}   ·   "
            f"Pend {backlog}   ·   {doing_text}   ·   Hecho {done}{badge_text}"
        )

    def _refresh_border(self) -> None:
        weight = "heavy" if self.is_active else "solid"
        if self.is_paused:
            color = "#8a8a8a" if self.is_active else "#4a4a4a"
            self.styles.border_top = ("solid", color)
            return
        ratio = lane_freshness(self.tasks, self.priority or 0, self.created_at)
        color = _gradient_color(ratio)
        self.styles.border_top = (weight, color)
        self.styles.background = Color.parse(color).with_alpha(0.08)

    @property
    def columns(self) -> list[Column]:
        return self._columns

    @property
    def active_column(self) -> Column:
        return self._columns[self.active_column_index]

    def doing_count(self) -> int:
        return sum(1 for task in self.tasks if task.status == Status.DOING)

    def set_tasks(self, tasks: list[Task], settings: BoardSettings | None = None) -> None:
        self.tasks = tasks
        by_status: dict[Status, list[Task]] = {s: [] for s in STATUS_ORDER}
        for task in tasks:
            by_status[task.status].append(task)
        id_to_task = {t.id: t for t in tasks}
        for column in self._columns:
            column.set_tasks(by_status[column.status], id_to_task, settings)
        if self._title is not None:
            self._title.update(self._header_text())
        self._refresh_border()
        self._dirty = True
        if self.is_active:
            self._render_columns()

    def _render_columns(self) -> None:
        for i, column in enumerate(self._columns):
            column.is_active = i == self.active_column_index
            column.render_page()
        self._dirty = False

    def _refresh_active_column(self) -> None:
        for i, column in enumerate(self._columns):
            column.set_active(self.is_active and i == self.active_column_index)

    def watch_is_active(self, value: bool) -> None:
        self.set_class(value, "active-lane")
        if self._body is not None:
            self._body.display = value
        if value:
            if self._dirty:
                self._render_columns()
            else:
                self._refresh_active_column()
        else:
            self._refresh_active_column()
        self._refresh_border()

    def focus_left(self) -> None:
        self.active_column_index = max(0, self.active_column_index - 1)
        self._refresh_active_column()

    def focus_right(self) -> None:
        self.active_column_index = min(len(STATUS_ORDER) - 1, self.active_column_index + 1)
        self._refresh_active_column()

    def move_selection(self, delta: int) -> None:
        self.active_column.move_selection(delta)

    def change_page(self, delta: int) -> None:
        self.active_column.change_page(delta)

    def get_selected_task(self) -> Task | None:
        return self.active_column.get_selected_task()

    def select_task_by_id(self, task_id: str) -> bool:
        for i, column in enumerate(self._columns):
            for j, task in enumerate(column.tasks):
                if task.id == task_id:
                    self.active_column_index = i
                    column.selected_index = j
                    if self.is_active:
                        self._render_columns()
                    else:
                        self._dirty = True
                    return True
        return False
