from __future__ import annotations

from datetime import date

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Static

from ..models import Status, Task, oneline
from ..settings import BoardSettings
from ..wip_rules import lane_freshness
from .column import Column

STATUS_ORDER = [Status.BACKLOG, Status.DOING, Status.DONE]

# Frescura del carril (ver lane_freshness) como medidor de bloques junto al
# nombre: lleno = verde (recién se terminó algo), vacío = rojo (lleva todo
# su ritmo sin terminar nada). Sin colores, así se lee en blanco y negro.
METER_WIDTH = 8


def freshness_meter(ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    filled = round((1.0 - ratio) * METER_WIDTH)
    if ratio < 0.34:
        word = "fresco"
    elif ratio < 0.67:
        word = "tibio"
    else:
        word = "frío"
    return f"▕{'█' * filled}{'░' * (METER_WIDTH - filled)}▏ {word}"


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
        self._cells: list[Static] = []
        self._body: Horizontal | None = None
        self._dirty = True
        self.add_class("objective-lane")
        if is_paused:
            self.add_class("paused-lane")

    def compose(self) -> ComposeResult:
        # Las dos filas de cabecera usan las mismas tres celdas que las
        # columnas, para que las líneas verticales nunca pisen texto.
        self._cells = [Static("", classes=f"lane-cell cell-{s.value}") for s in STATUS_ORDER]
        yield Horizontal(*self._cells, classes="lane-row lane-header")
        description = oneline(self.description) if self.description else "(sin descripción)"
        yield Horizontal(
            Static(escape(description), classes="lane-cell lane-description cell-backlog"),
            Static("", classes="lane-cell cell-doing"),
            Static("", classes="lane-cell cell-done"),
            classes="lane-row",
        )
        self._columns = [Column(status, lane_key=self.lane_key) for status in STATUS_ORDER]
        self._body = Horizontal(*self._columns, classes="lane-body")
        self._body.display = False
        yield self._body

    def _header_cells(self) -> tuple[str, str, str]:
        backlog = sum(1 for t in self.tasks if t.status == Status.BACKLOG)
        doing = sum(1 for t in self.tasks if t.status == Status.DOING)
        done = sum(1 for t in self.tasks if t.status == Status.DONE)

        if self.wip_limit is not None:
            doing_text = f"Prog {doing}/{self.wip_limit}"
            if doing >= self.wip_limit:
                doing_text = f"[bold $error]{doing_text}[/]"
        else:
            doing_text = f"Prog {doing}"

        if self.is_paused:
            meter = "(apagado)"
        else:
            meter = freshness_meter(lane_freshness(self.tasks, self.priority or 0, self.created_at))

        first = (
            f"[bold]{escape(self.title_text)}[/bold]  {meter}  ·  "
            f"P{self.priority}  ·  Pend {backlog}"
        )
        return first, doing_text, f"Hecho {done}"

    def _refresh_header(self) -> None:
        if self._cells:
            for cell, text in zip(self._cells, self._header_cells()):
                cell.update(text)

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
        self._refresh_header()
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
