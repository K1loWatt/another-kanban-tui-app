from __future__ import annotations

from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Static

from . import objectives, storage
from .config import get_tasks_dir
from .models import ServiceClass, Status, Task
from .screens.confirm import ConfirmScreen
from .screens.metrics_screen import MetricsScreen
from .screens.objective_summary_screen import ObjectiveSummaryScreen
from .screens.objectives_screen import ObjectivesScreen
from .screens.task_form import TaskFormScreen
from .widgets.column import STATUS_TITLES
from .widgets.lane import STATUS_ORDER, Lane
from .widgets.task_card import TaskCard


class KanbanApp(App):
    """Un tablero kanban de terminal con carriles por objetivo, respaldado por markdown."""

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
        Binding("shift+up,K", "prev_lane", "Carril ↑"),
        Binding("shift+down,J", "next_lane", "Carril ↓"),
        Binding("c", "close_active_lane", "Cerrar carril"),
        Binding("s", "show_objective_summary", "Resumen"),
        Binding("o", "manage_objectives", "Objetivos"),
        Binding("m", "show_metrics", "Métricas"),
        Binding("r", "reload", "Recargar"),
        Binding("q", "quit", "Salir"),
    ]

    def __init__(self, tasks_dir: Path | None = None) -> None:
        super().__init__()
        self.tasks_dir = tasks_dir or get_tasks_dir()
        storage.ensure_tasks_dir(self.tasks_dir)
        objectives.ensure_default_objective(self.tasks_dir)
        self.active_lane_index = 0
        self._last_signature: tuple = ()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="board-header"):
            for status in STATUS_ORDER:
                yield Static(STATUS_TITLES[status], classes="board-col-header")
        with VerticalScroll(id="board"):
            yield Lane(
                "urgent",
                "Urgencias",
                is_urgency=True,
                wip_limit=objectives.EXPEDITE_DOING_LIMIT,
                id="lane-urgent",
            )
            for objective in self._active_objectives():
                yield Lane(
                    objective.id,
                    objective.name,
                    objective_id=objective.id,
                    priority=objective.priority,
                    description=objective.description,
                    wip_limit=objectives.LANE_WIP_LIMIT,
                    id=f"lane-{objective.id}",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = str(self.tasks_dir)
        self._migrate_task_objectives()
        self.reload_tasks()
        self._refresh_active()
        self.set_interval(0.8, self._toggle_blink)
        self.set_interval(3.0, self._check_external_changes)

    def _active_objectives(self) -> list[objectives.Objective]:
        return sorted(
            objectives.active_objectives(objectives.load_objectives(self.tasks_dir)),
            key=lambda o: (o.priority, o.created_at),
        )

    def _migrate_task_objectives(self) -> None:
        active = self._active_objectives()
        default_name = active[0].name if active else objectives.DEFAULT_OBJECTIVE_NAME
        tasks = storage.load_all_tasks(self.tasks_dir)
        storage.migrate_missing_objectives(self.tasks_dir, tasks, default_name)

    @property
    def lanes(self) -> list[Lane]:
        return list(self.query(Lane))

    @property
    def active_lane(self) -> Lane:
        lanes = self.lanes
        idx = max(0, min(self.active_lane_index, len(lanes) - 1))
        return lanes[idx]

    async def rebuild_board(self) -> None:
        board = self.query_one("#board", VerticalScroll)
        await board.remove_children()
        await board.mount(
            Lane(
                "urgent",
                "Urgencias",
                is_urgency=True,
                wip_limit=objectives.EXPEDITE_DOING_LIMIT,
                id="lane-urgent",
            )
        )
        for objective in self._active_objectives():
            await board.mount(
                Lane(
                    objective.id,
                    objective.name,
                    objective_id=objective.id,
                    priority=objective.priority,
                    description=objective.description,
                    wip_limit=objectives.LANE_WIP_LIMIT,
                    id=f"lane-{objective.id}",
                )
            )
        self.active_lane_index = 0
        self.reload_tasks()
        self._refresh_active()

    def reload_tasks(self, keep_selection: bool = False) -> None:
        selected_id = None
        if keep_selection:
            task = self.active_lane.get_selected_task()
            selected_id = task.id if task else None

        tasks = storage.load_all_tasks(self.tasks_dir)
        storage.escalate_due_dates(self.tasks_dir, tasks)
        for lane in self.lanes:
            if lane.is_urgency:
                lane_tasks = [t for t in tasks if t.service_class == ServiceClass.EXPEDITE]
            else:
                lane_tasks = [t for t in tasks if t.objective == lane.title_text]
            lane.set_tasks(lane_tasks)

        if selected_id:
            self.select_task_by_id(selected_id)

        self._last_signature = storage.dir_signature(self.tasks_dir)
        self._refresh_active()

    def _refresh_active(self) -> None:
        lanes = self.lanes
        if not lanes:
            return
        self.active_lane_index = max(0, min(self.active_lane_index, len(lanes) - 1))
        for i, lane in enumerate(lanes):
            lane.is_active = i == self.active_lane_index

    def action_focus_left(self) -> None:
        self.active_lane.focus_left()

    def action_focus_right(self) -> None:
        self.active_lane.focus_right()

    def action_focus_up(self) -> None:
        self.active_lane.move_selection(-1)

    def action_focus_down(self) -> None:
        self.active_lane.move_selection(1)

    def action_prev_lane(self) -> None:
        self.active_lane_index = max(0, self.active_lane_index - 1)
        self._refresh_active()

    def action_next_lane(self) -> None:
        lanes = self.lanes
        self.active_lane_index = min(len(lanes) - 1, self.active_lane_index + 1)
        self._refresh_active()

    def action_new_task(self) -> None:
        lane = self.active_lane
        status = lane.active_column.status
        default_objective = "" if lane.is_urgency else lane.title_text
        objective_names = [o.name for o in self._active_objectives()]
        other_tasks = storage.load_all_tasks(self.tasks_dir)

        def handle(task: Task | None) -> None:
            if task is None:
                return
            storage.save_task(self.tasks_dir, task)
            self.reload_tasks()
            self.select_task_by_id(task.id)

        self.push_screen(
            TaskFormScreen(
                default_status=status,
                objective_names=objective_names,
                default_objective=default_objective,
                other_tasks=other_tasks,
            ),
            handle,
        )

    def action_edit_task(self) -> None:
        task = self.active_lane.get_selected_task()
        if task is not None:
            self.edit_task(task)

    def edit_task(self, task: Task) -> None:
        objective_names = [o.name for o in self._active_objectives()]
        other_tasks = [t for t in storage.load_all_tasks(self.tasks_dir) if t.id != task.id]

        def handle(updated: Task | None) -> None:
            if updated is None:
                return
            storage.save_task(self.tasks_dir, updated)
            self.reload_tasks()
            self.select_task_by_id(updated.id)

        self.push_screen(
            TaskFormScreen(task=task, objective_names=objective_names, other_tasks=other_tasks),
            handle,
        )

    def action_delete_task(self) -> None:
        task = self.active_lane.get_selected_task()
        if task is None:
            return

        def handle(confirmed: bool) -> None:
            if confirmed:
                storage.delete_task(task)
                self.reload_tasks()

        self.push_screen(ConfirmScreen(f"¿Eliminar '{task.title}'?"), handle)

    def _move_active_task(self, delta: int) -> None:
        lane = self.active_lane
        task = lane.get_selected_task()
        if task is None:
            return
        idx = STATUS_ORDER.index(task.status)
        new_idx = idx + delta
        if not (0 <= new_idx < len(STATUS_ORDER)):
            return
        new_status = STATUS_ORDER[new_idx]

        if new_status == Status.DOING:
            limit = (
                objectives.EXPEDITE_DOING_LIMIT
                if task.service_class == ServiceClass.EXPEDITE
                else objectives.LANE_WIP_LIMIT
            )
            doing_count = sum(1 for t in lane.tasks if t.status == Status.DOING and t.id != task.id)
            if doing_count >= limit:
                self.notify(f"Límite de WIP ({limit}) alcanzado en este carril.", severity="error")
                return

        task.status = new_status
        if task.status == Status.DOING and task.started_at is None:
            task.started_at = date.today()
        elif task.status != Status.DOING and task.status != Status.DONE:
            task.started_at = None

        if task.status == Status.DONE and task.completed_at is None:
            task.completed_at = date.today()
        elif task.status != Status.DONE:
            task.completed_at = None

        storage.save_task(self.tasks_dir, task)
        self.reload_tasks()
        self.select_task_by_id(task.id)

    def action_move_left(self) -> None:
        self._move_active_task(-1)

    def action_move_right(self) -> None:
        self._move_active_task(1)

    def action_reload(self) -> None:
        self.reload_tasks(keep_selection=True)
        self.notify("Recargado desde el disco")

    def action_manage_objectives(self) -> None:
        async def handle(changed: bool) -> None:
            if changed:
                await self.rebuild_board()

        self.push_screen(ObjectivesScreen(self.tasks_dir), handle)

    def action_show_metrics(self) -> None:
        self.push_screen(MetricsScreen(self.tasks_dir))

    def action_show_objective_summary(self) -> None:
        lane = self.active_lane
        self.push_screen(
            ObjectiveSummaryScreen(
                lane.title_text,
                is_urgency=lane.is_urgency,
                priority=lane.priority,
                wip_limit=lane.wip_limit,
                tasks=lane.tasks,
            )
        )

    def action_close_active_lane(self) -> None:
        lane = self.active_lane
        if lane.is_urgency:
            self.notify("El carril de Urgencias no se puede cerrar.", severity="warning")
            return
        self.close_lane(lane.objective_id)

    def close_lane(self, objective_id: str | None) -> None:
        if objective_id is None:
            return
        objective = next(
            (o for o in objectives.load_objectives(self.tasks_dir) if o.id == objective_id), None
        )
        if objective is None:
            return
        unfinished = sum(
            1
            for t in storage.load_all_tasks(self.tasks_dir)
            if t.objective == objective.name and t.status != Status.DONE
        )

        def finalize() -> None:
            objectives.close_objective(self.tasks_dir, objective_id)
            self.run_worker(self.rebuild_board(), exclusive=False)
            self.notify(f"Carril «{objective.name}» cerrado")

        def handle_confirm(confirmed: bool) -> None:
            if confirmed:
                finalize()

        if unfinished:
            message = (
                f"«{objective.name}» tiene {unfinished} tarea(s) sin terminar. Si lo cierras, "
                "quedarán archivadas junto al objetivo y desaparecerán del tablero. "
                "¿Cerrar igualmente?"
            )
        else:
            message = f"¿Cerrar el carril «{objective.name}»?"

        self.push_screen(ConfirmScreen(message, confirm_label="Cerrar carril"), handle_confirm)

    def select_task_by_id(self, task_id: str) -> None:
        for i, lane in enumerate(self.lanes):
            if lane.select_task_by_id(task_id):
                self.active_lane_index = i
                self._refresh_active()
                return

    def select_card(self, task: Task) -> None:
        self.select_task_by_id(task.id)
        self.edit_task(task)

    def _toggle_blink(self) -> None:
        if not self.is_running:
            return
        try:
            lanes = self.lanes
        except NoMatches:
            return
        for lane in lanes:
            for card in lane.query(TaskCard):
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
