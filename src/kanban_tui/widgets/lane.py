from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widgets import Static

from ..models import Status, Task, oneline
from ..settings import BoardSettings
from .column import Column

STATUS_ORDER = [Status.BACKLOG, Status.DOING, Status.DONE]


class Lane(Vertical):
    """Un carril horizontal del tablero: el de urgencias, o uno por objetivo."""

    is_active: reactive[bool] = reactive(False)
    needs_intangible: reactive[bool] = reactive(False)

    def __init__(
        self,
        lane_key: str,
        title: str,
        *,
        is_urgency: bool = False,
        objective_id: str | None = None,
        priority: int | None = None,
        description: str = "",
        wip_limit: int | None = None,
        is_paused: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.lane_key = lane_key
        self.title_text = title
        self.is_urgency = is_urgency
        self.objective_id = objective_id
        self.priority = priority
        self.description = description
        self.wip_limit = wip_limit
        self.is_paused = is_paused
        self.active_column_index = 0
        self.tasks: list[Task] = []
        self.add_class("urgency-lane" if is_urgency else "objective-lane")
        if is_paused:
            self.add_class("paused-lane")

    def compose(self) -> ComposeResult:
        with Horizontal(classes="lane-header"):
            yield Static(self._header_text(), classes="lane-title", id=f"lane-title-{self.lane_key}")
        if not self.is_urgency:
            description = oneline(self.description) if self.description else "(sin descripción)"
            yield Static(f"   {description}", classes="lane-description")
        with Horizontal(classes="lane-body"):
            for status in STATUS_ORDER:
                wip = self.wip_limit if status == Status.DOING else None
                yield Column(status, lane_key=self.lane_key, wip_limit=wip, id=f"column-{self.lane_key}-{status.value}")

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

        if self.is_urgency:
            return (
                f"\U0001f6a8 [bold]URGENCIAS[/bold]   ·   Pend {backlog}   ·   "
                f"{doing_text}   ·   Hecho {done}"
            )

        badges = []
        if self.is_paused:
            badges.append("[dim]⏸ apagado[/dim]")
        if self.needs_intangible:
            badges.append("[bold #d9b36c]💡 toca intangible[/]")
        badge_text = "   ·   " + "   ·   ".join(badges) if badges else ""

        return (
            f"\U0001f3af [bold]{escape(self.title_text)}[/bold]   ·   P{self.priority}   ·   "
            f"Pend {backlog}   ·   {doing_text}   ·   Hecho {done}{badge_text}"
        )

    def set_flags(self, *, needs_intangible: bool = False) -> None:
        self.needs_intangible = needs_intangible
        self._refresh_header()

    def _refresh_header(self) -> None:
        try:
            self.query_one(f"#lane-title-{self.lane_key}", Static).update(self._header_text())
        except NoMatches:
            pass

    @property
    def columns(self) -> list[Column]:
        return [self.query_one(f"#column-{self.lane_key}-{s.value}", Column) for s in STATUS_ORDER]

    @property
    def active_column(self) -> Column:
        return self.columns[self.active_column_index]

    def doing_count(self) -> int:
        return sum(1 for task in self.tasks if task.status == Status.DOING)

    def set_tasks(self, tasks: list[Task], settings: BoardSettings | None = None) -> None:
        self.tasks = tasks
        by_status: dict[Status, list[Task]] = {s: [] for s in STATUS_ORDER}
        for task in tasks:
            by_status[task.status].append(task)
        id_to_task = {t.id: t for t in tasks}
        for column in self.columns:
            column.set_tasks(by_status[column.status], id_to_task, settings)
        self._refresh_header()
        self._refresh_active_column()

    def _refresh_active_column(self) -> None:
        for i, column in enumerate(self.columns):
            column.is_active = self.is_active and i == self.active_column_index

    def watch_is_active(self, value: bool) -> None:
        self.set_class(value, "active-lane")
        self._refresh_active_column()

    def focus_left(self) -> None:
        self.active_column_index = max(0, self.active_column_index - 1)
        self._refresh_active_column()

    def focus_right(self) -> None:
        self.active_column_index = min(len(STATUS_ORDER) - 1, self.active_column_index + 1)
        self._refresh_active_column()

    def move_selection(self, delta: int) -> None:
        self.active_column.move_selection(delta)

    def get_selected_task(self) -> Task | None:
        return self.active_column.get_selected_task()

    def select_task_by_id(self, task_id: str) -> bool:
        for i, column in enumerate(self.columns):
            for j, task in enumerate(column.tasks):
                if task.id == task_id:
                    self.active_column_index = i
                    column.selected_index = j
                    self._refresh_active_column()
                    return True
        return False
