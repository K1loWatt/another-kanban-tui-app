from __future__ import annotations

from datetime import date
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Static

from . import __version__, objectives, recurring, storage, wip_rules
from .config import DEFAULT_THEME, get_tasks_dir, get_theme, save_theme
from .models import ServiceClass, Status, Task
from .screens.confirm import ConfirmScreen
from .screens.metrics_screen import MetricsScreen
from .screens.objective_summary_screen import ObjectiveSummaryScreen
from .screens.objectives_screen import ObjectivesScreen
from .screens.recurring_screen import RecurringScreen
from .screens.settings_screen import SettingsScreen
from .screens.task_detail_screen import TaskDetailScreen
from .screens.task_form import TaskFormScreen
from .screens.wip_screen import WipScreen
from .settings import load_settings
from .themes import CUSTOM_THEMES
from .widgets.column import STATUS_TITLES
from .widgets.lane import STATUS_ORDER, Lane


STATS_BAR_WIDTH = 20


class BoardHeader(Horizontal):
    """Fila de títulos de columna. Al cambiar de tamaño (ya con el layout
    nuevo calculado) recoloca las líneas verticales del tablero."""

    def on_resize(self, event) -> None:
        self.app._place_separators()


class Board(VerticalScroll):
    """El tablero con los carriles. Si solo cambia de alto (la fila de títulos
    no se entera), también recoloca las líneas verticales."""

    def on_resize(self, event) -> None:
        self.app._place_separators()


class KanbanApp(App):
    """Un tablero kanban de terminal con carriles por objetivo, respaldado por markdown."""

    CSS_PATH = "kanban.tcss"
    TITLE = "Tablero Kanban"

    BINDINGS = [
        Binding("n", "new_task", "Nueva"),
        Binding("enter,e", "edit_task", "Editar", key_display="enter"),
        Binding("d", "view_task", "Detalle"),
        Binding("v", "delete_task", "Archivar"),
        Binding("f12", "show_wip", "En curso"),
        Binding("left,h", "focus_left", "Columna", show=True),
        Binding("right,l", "focus_right", "Columna", show=False),
        Binding("up,k", "focus_up", "Arriba", show=False),
        Binding("down,j", "focus_down", "Abajo", show=False),
        Binding("comma", "move_left", "← Retroceder"),
        Binding("full_stop", "move_right", "Avanzar →"),
        Binding("shift+tab", "prev_lane", "Carril ↑", priority=True),
        Binding("tab", "next_lane", "Carril ↓", priority=True),
        Binding("pageup", "jump_up", "Pág ↑", show=False, priority=True),
        Binding("pagedown", "jump_down", "Pág ↓", show=False, priority=True),
        Binding("c", "close_active_lane", "Cerrar carril"),
        Binding("p", "toggle_pause_lane", "Apagar/Encender"),
        Binding("f", "finish_and_next", "Terminar y crear siguiente"),
        Binding("s", "show_objective_summary", "Resumen"),
        Binding("o", "manage_objectives", "Objetivos"),
        Binding("R", "show_recurring", "Recarga"),
        Binding("a", "open_settings", "Ajustes"),
        Binding("m", "show_metrics", "Métricas"),
        Binding("r", "reload", "Recargar"),
        Binding("q", "quit", "Salir"),
    ]

    def __init__(self, tasks_dir: Path | None = None) -> None:
        super().__init__()
        # Solo temas de Textual (se cambian con ctrl+p); el elegido se
        # recuerda en ~/.config/kanban-tui/config.json.
        for custom_theme in CUSTOM_THEMES:
            self.register_theme(custom_theme)
        theme = get_theme()
        self.theme = theme if theme in self.available_themes else DEFAULT_THEME
        self.tasks_dir = tasks_dir or get_tasks_dir()
        storage.ensure_tasks_dir(self.tasks_dir)
        objectives.ensure_default_objective(self.tasks_dir)
        self.active_lane_index = 0
        self._last_signature: tuple = ()
        # Caché en memoria: los cambios hechos desde la propia app actualizan
        # esto y solo repintan los carriles afectados, sin releer el disco.
        self._tasks: list[Task] = []
        self._lanes: list[Lane] = []
        self._settings = load_settings(self.tasks_dir)
        self._health = 1.0

    def compose(self) -> ComposeResult:
        yield Header(icon="≡")
        yield Static("", id="stats-banner")
        with BoardHeader(id="board-header"):
            for status in STATUS_ORDER:
                yield Static(
                    STATUS_TITLES[status], classes=f"board-col-header header-{status.value}"
                )
        with Board(id="board"):
            for objective in self._visible_objectives():
                yield Lane(
                    objective.id,
                    objective.name,
                    objective_id=objective.id,
                    priority=objective.priority,
                    description=objective.description,
                    is_paused=objective.is_paused,
                    created_at=objective.created_at,
                    id=f"lane-{objective.id}",
                )
        yield Footer()
        for status in STATUS_ORDER[1:]:
            yield Static("", classes="col-separator", id=f"sep-{status.value}")

    def watch_theme(self, theme: str) -> None:
        save_theme(theme)

    def on_mount(self) -> None:
        self.title = f"Tablero Kanban v{__version__}"
        self.sub_title = str(self.tasks_dir)
        self._migrate_task_objectives()
        self._lanes = list(self.query(Lane))
        self.reload_tasks()
        self.set_interval(5.0, self._check_external_changes)
        self.call_after_refresh(self._place_separators)

    def _place_separators(self) -> None:
        """Coloca las dos líneas verticales justo sobre el borde izquierdo de
        las columnas En progreso / Hecho, desde la fila de títulos hasta el
        final del tablero, para que la separación sea continua entre carriles."""
        try:
            header = self.query_one("#board-header")
            board = self.query_one("#board", VerticalScroll)
        except NoMatches:
            return
        top = header.region.y
        height = max(1, board.region.bottom - top)
        for status in STATUS_ORDER[1:]:
            sep = self.query_one(f"#sep-{status.value}", Static)
            cell = header.query_one(f".header-{status.value}")
            sep.styles.offset = (cell.region.x, top)
            sep.styles.height = height
            sep.update("\n".join("│" * height))

    def _active_objectives(self) -> list[objectives.Objective]:
        return sorted(
            objectives.active_objectives(objectives.load_objectives(self.tasks_dir)),
            key=lambda o: (o.priority, o.created_at),
        )

    def _visible_objectives(self) -> list[objectives.Objective]:
        """Objetivos a mostrar como carril: activos primero, apagados al final."""
        return sorted(
            objectives.visible_objectives(objectives.load_objectives(self.tasks_dir)),
            key=lambda o: (o.is_paused, o.priority, o.created_at),
        )

    def _migrate_task_objectives(self) -> None:
        active = self._active_objectives()
        default_name = active[0].name if active else objectives.DEFAULT_OBJECTIVE_NAME
        tasks = storage.load_all_tasks(self.tasks_dir)
        storage.migrate_missing_objectives(self.tasks_dir, tasks, default_name)

    # Acciones que dependen de que exista al menos un carril en el tablero.
    _LANE_ACTIONS = {
        "new_task", "edit_task", "view_task", "delete_task", "focus_left", "focus_right",
        "focus_up", "focus_down", "move_left", "move_right", "close_active_lane",
        "toggle_pause_lane", "finish_and_next", "show_objective_summary",
        "jump_up", "jump_down", "prev_lane", "next_lane",
    }

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Sin carriles (todos los objetivos cerrados o borrados) estas acciones
        # no tienen sobre qué actuar. Con un popup abierto, jump/next/prev
        # siguen funcionando (scroll / cambio de campo).
        if self._modal_active:
            # Con un popup abierto, las teclas del tablero (n, d, v, ...) no
            # deben actuar por debajo; solo las que el popup reutiliza.
            return action in self._MODAL_ACTIONS
        if action in self._LANE_ACTIONS and not self.lanes:
            return False
        return True

    _MODAL_ACTIONS = {"jump_up", "jump_down", "prev_lane", "next_lane", "quit"}

    @property
    def lanes(self) -> list[Lane]:
        return self._lanes

    @property
    def active_lane(self) -> Lane:
        lanes = self.lanes
        idx = max(0, min(self.active_lane_index, len(lanes) - 1))
        return lanes[idx]

    async def rebuild_board(self) -> None:
        board = self.query_one("#board", VerticalScroll)
        await board.remove_children()
        for objective in self._visible_objectives():
            await board.mount(
                Lane(
                    objective.id,
                    objective.name,
                    objective_id=objective.id,
                    priority=objective.priority,
                    description=objective.description,
                    is_paused=objective.is_paused,
                    created_at=objective.created_at,
                    id=f"lane-{objective.id}",
                )
            )
        self._lanes = list(self.query(Lane))
        self.active_lane_index = 0
        self.reload_tasks()

    @staticmethod
    def _stats_banner_text(
        doing_global: int, global_wip_limit: int, intangible_debt: int, health: float
    ) -> str:
        wip_text = (
            f"[bold]WIP global: {doing_global}/{global_wip_limit}[/]"
            if doing_global < global_wip_limit
            else f"[bold $error]WIP global: {doing_global}/{global_wip_limit} (al límite)[/]"
        )
        intangible_text = f"[bold]Intangibles pendientes: {intangible_debt}[/]"
        pct = round(health * 100)
        filled = round(health * STATS_BAR_WIDTH)
        bar = "█" * filled + "░" * (STATS_BAR_WIDTH - filled)
        health_text = f"Recarga Energía — [bold]{pct}%[/]  {bar}"
        return f"{wip_text}   ·   {intangible_text}   ·   {health_text}"

    def reload_tasks(self, keep_selection: bool = False) -> None:
        """Recarga completa desde el disco (arranque, `r`, cambios externos,
        objetivos/ajustes). Los cambios hechos desde la app usan
        `_commit_task`, que no relee nada."""
        selected_id = None
        if keep_selection and self.lanes:
            task = self.active_lane.get_selected_task()
            selected_id = task.id if task else None

        settings = self._settings = load_settings(self.tasks_dir)
        tasks = storage.load_active_tasks(self.tasks_dir)
        storage.escalate_due_dates(
            self.tasks_dir,
            tasks,
            due_soon_days=settings.due_soon_days,
            due_soon_cap=settings.due_soon_priority_cap,
            due_urgent_days=settings.due_urgent_days,
            due_urgent_cap=settings.due_urgent_priority_cap,
        )
        self._tasks = tasks
        self._health = recurring.recurring_health(recurring.load_recurring_tasks(self.tasks_dir))

        for lane in self.lanes:
            lane.set_tasks(self._lane_tasks(lane.title_text), settings=settings)

        if selected_id:
            self.select_task_by_id(selected_id)

        self._update_banner()
        self._last_signature = storage.dir_signature(self.tasks_dir)
        self._refresh_active()

    def _lane_tasks(self, objective_name: str) -> list[Task]:
        return [t for t in self._tasks if t.objective == objective_name]

    def _update_banner(self) -> None:
        visible_names = [lane.title_text for lane in self.lanes]
        doing_global = wip_rules.global_doing_count(self._tasks, visible_names=visible_names)
        intangible_debt = wip_rules.intangible_debt(self._tasks)
        self.query_one("#stats-banner", Static).update(
            self._stats_banner_text(
                doing_global, self._settings.global_wip_limit, intangible_debt, self._health
            )
        )

    def _commit_task(self, task: Task, old_objective: str | None = None) -> None:
        """Guarda una tarea y actualiza solo lo que cambia: la caché en
        memoria, los carriles de su objetivo (y del anterior, si se movió de
        carril) y el banner. Nada de releer todo el disco."""
        storage.save_task(self.tasks_dir, task)
        self._tasks = [t for t in self._tasks if t.id != task.id]
        if not task.archived:
            self._tasks.append(task)
        affected = {task.objective, old_objective}
        for lane in self.lanes:
            if lane.title_text in affected:
                lane.set_tasks(self._lane_tasks(lane.title_text), settings=self._settings)
        self._update_banner()
        # Que el sondeo de cambios externos no confunda este guardado con
        # una edición hecha en otra máquina.
        self._last_signature = storage.dir_signature(self.tasks_dir)

    def _refresh_active(self) -> None:
        lanes = self.lanes
        if not lanes:
            return
        self.active_lane_index = max(0, min(self.active_lane_index, len(lanes) - 1))
        for i, lane in enumerate(lanes):
            lane.is_active = i == self.active_lane_index
        active = lanes[self.active_lane_index]
        self.call_after_refresh(active.scroll_visible, animate=False)

    def action_focus_left(self) -> None:
        self.active_lane.focus_left()

    def action_focus_right(self) -> None:
        self.active_lane.focus_right()

    def action_focus_up(self) -> None:
        self.active_lane.move_selection(-1)

    def action_focus_down(self) -> None:
        self.active_lane.move_selection(1)

    def action_jump_up(self) -> None:
        if self._modal_active:
            self._scroll_modal_body(-1)
            return
        self.active_lane.change_page(-1)

    def action_jump_down(self) -> None:
        if self._modal_active:
            self._scroll_modal_body(1)
            return
        self.active_lane.change_page(1)

    def action_prev_lane(self) -> None:
        if self._modal_active:
            self.screen.focus_previous()
            return
        self.active_lane_index = max(0, self.active_lane_index - 1)
        self._refresh_active()

    def action_next_lane(self) -> None:
        if self._modal_active:
            self.screen.focus_next()
            return
        lanes = self.lanes
        self.active_lane_index = min(len(lanes) - 1, self.active_lane_index + 1)
        self._refresh_active()

    @property
    def _modal_active(self) -> bool:
        """True mientras haya una pantalla (popup) encima del tablero principal."""
        return len(self.screen_stack) > 1

    def _scroll_modal_body(self, direction: int) -> None:
        try:
            body = self.screen.query(VerticalScroll).first()
        except NoMatches:
            return
        if direction > 0:
            body.scroll_page_down()
        else:
            body.scroll_page_up()

    def action_new_task(self) -> None:
        lane = self.active_lane
        status = lane.active_column.status
        default_objective = lane.title_text
        objective_names = [o.name for o in self._visible_objectives()]
        other_tasks = list(self._tasks)
        settings = self._settings

        def handle(task: Task | None) -> None:
            if task is None:
                return
            self._commit_task(task)
            self.select_task_by_id(task.id)

        self.push_screen(
            TaskFormScreen(
                default_status=status,
                objective_names=objective_names,
                default_objective=default_objective,
                other_tasks=other_tasks,
                settings=settings,
            ),
            handle,
        )

    def action_edit_task(self) -> None:
        task = self.active_lane.get_selected_task()
        if task is not None:
            self.edit_task(task)

    def edit_task(self, task: Task) -> None:
        objective_names = [o.name for o in self._visible_objectives()]
        other_tasks = [t for t in self._tasks if t.id != task.id]
        settings = self._settings
        old_objective = task.objective

        def handle(updated: Task | None) -> None:
            if updated is None:
                return
            self._commit_task(updated, old_objective=old_objective)
            self.select_task_by_id(updated.id)

        self.push_screen(
            TaskFormScreen(
                task=task,
                objective_names=objective_names,
                other_tasks=other_tasks,
                settings=settings,
            ),
            handle,
        )

    def action_view_task(self) -> None:
        task = self.active_lane.get_selected_task()
        if task is None:
            return

        def handle(changed: bool) -> None:
            if changed:
                self.reload_tasks(keep_selection=True)

        self.push_screen(TaskDetailScreen(task, self.tasks_dir), handle)

    def action_finish_and_next(self) -> None:
        """Marca la tarea seleccionada como Hecho y abre directamente el
        formulario para crear la siguiente tarea del backlog en el mismo carril."""
        lane = self.active_lane
        task = lane.get_selected_task()
        if task is None:
            return

        self.mark_task_done(task)

        default_objective = lane.title_text
        objective_names = [o.name for o in self._visible_objectives()]
        other_tasks = list(self._tasks)
        settings = self._settings

        def handle(new_task: Task | None) -> None:
            if new_task is None:
                return
            self._commit_task(new_task)
            self.select_task_by_id(new_task.id)

        self.push_screen(
            TaskFormScreen(
                default_status=Status.BACKLOG,
                objective_names=objective_names,
                default_objective=default_objective,
                other_tasks=other_tasks,
                settings=settings,
            ),
            handle,
        )

    def mark_task_done(self, task: Task) -> None:
        task.status = Status.DONE
        if task.completed_at is None:
            task.completed_at = date.today()
        self._commit_task(task)

    def action_show_wip(self) -> None:
        visible = {lane.title_text for lane in self.lanes}
        doing = [t for t in self._tasks if t.status == Status.DOING and t.objective in visible]

        def handle(comments_changed: bool) -> None:
            if comments_changed:
                self.reload_tasks(keep_selection=True)

        self.push_screen(WipScreen(doing, self.tasks_dir, on_done=self.mark_task_done), handle)

    def action_delete_task(self) -> None:
        task = self.active_lane.get_selected_task()
        if task is None:
            return

        def handle(confirmed: bool) -> None:
            if confirmed:
                task.archived = True
                self._commit_task(task)
                self.notify(f"«{task.title}» archivada (el archivo sigue en disco)")

        self.push_screen(
            ConfirmScreen(
                f"¿Archivar '{task.title}'? Desaparece del tablero pero nunca se borra del disco.",
                confirm_label="Archivar",
            ),
            handle,
        )

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
            all_tasks = self._tasks
            settings = self._settings

            if task.blocked_by:
                blocker = next((t for t in all_tasks if t.id == task.blocked_by), None)
                if blocker is not None and blocker.status != Status.DONE:
                    self.notify(
                        f"Bloqueada por «{blocker.title}». Termina esa tarea primero.",
                        severity="error",
                    )
                    return

            if task.service_class == ServiceClass.EXPEDITE:
                doing_count = sum(
                    1
                    for t in all_tasks
                    if t.service_class == ServiceClass.EXPEDITE
                    and t.status == Status.DOING
                    and t.id != task.id
                )
                if doing_count >= settings.expedite_doing_limit:
                    self.notify(
                        f"Límite de WIP ({settings.expedite_doing_limit}) alcanzado para tareas Expedito.",
                        severity="error",
                    )
                    return
            else:
                visible_names = [o.name for o in self._visible_objectives()]
                doing_count = wip_rules.global_doing_count(
                    all_tasks, excluding_id=task.id, visible_names=visible_names
                )
                if doing_count >= settings.global_wip_limit:
                    self.notify(
                        f"Límite global de WIP ({settings.global_wip_limit}) alcanzado. "
                        "Termina la tarea en curso antes de empezar otra.",
                        severity="error",
                    )
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

        self._commit_task(task)
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

    def action_show_recurring(self) -> None:
        def handle(changed: bool) -> None:
            if changed:
                self.reload_tasks(keep_selection=True)

        self.push_screen(RecurringScreen(self.tasks_dir), handle)

    def action_open_settings(self) -> None:
        def handle(new_tasks_dir: Path | None) -> None:
            if new_tasks_dir is None:
                return
            self.run_worker(self.switch_tasks_dir(new_tasks_dir), exclusive=False)

        self.push_screen(SettingsScreen(self.tasks_dir), handle)

    async def switch_tasks_dir(self, new_dir: Path) -> None:
        # Siempre se reconstruye el tablero (incluso si la carpeta no cambió),
        # porque los límites de WIP/objetivos se fijan en cada carril al
        # crearlo y hay que recogerlos si cambiaron en el panel de ajustes.
        changed_dir = new_dir != self.tasks_dir
        self.tasks_dir = new_dir
        storage.ensure_tasks_dir(self.tasks_dir)
        objectives.ensure_default_objective(self.tasks_dir)
        self.sub_title = str(self.tasks_dir)
        self._migrate_task_objectives()
        await self.rebuild_board()
        if changed_dir:
            self.notify(f"Carpeta de tareas cambiada a {self.tasks_dir}")
        else:
            self.notify("Ajustes guardados")

    def action_show_metrics(self) -> None:
        self.push_screen(MetricsScreen(self.tasks_dir))

    def action_show_objective_summary(self) -> None:
        lane = self.active_lane
        settings = self._settings
        self.push_screen(
            ObjectiveSummaryScreen(
                lane.title_text,
                priority=lane.priority,
                wip_limit=settings.global_wip_limit,
                tasks=lane.tasks,
            )
        )

    def action_close_active_lane(self) -> None:
        lane = self.active_lane
        self.close_lane(lane.objective_id)

    def action_toggle_pause_lane(self) -> None:
        lane = self.active_lane
        if lane.objective_id is None:
            return
        objective = next(
            (o for o in objectives.load_objectives(self.tasks_dir) if o.id == lane.objective_id), None
        )
        if objective is None:
            return
        if objective.is_active:
            objectives.pause_objective(self.tasks_dir, objective.id)
            self.notify(f"Carril «{objective.name}» apagado")
        elif objective.is_paused:
            max_active = load_settings(self.tasks_dir).max_active_objectives
            try:
                objectives.unpause_objective(self.tasks_dir, objective.id, max_active=max_active)
            except objectives.TooManyActiveObjectives as exc:
                self.notify(str(exc), severity="error")
                return
            self.notify(f"Carril «{objective.name}» encendido")
        else:
            return
        self.run_worker(self.rebuild_board(), exclusive=False)

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
            for t in self._tasks
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
            if any(t.id == task_id for t in lane.tasks) and lane.select_task_by_id(task_id):
                if i != self.active_lane_index:
                    self.active_lane_index = i
                    self._refresh_active()
                return

    def select_card(self, task: Task) -> None:
        self.select_task_by_id(task.id)
        self.edit_task(task)

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
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("-V", "--version"):
        print(f"kanban-tui {__version__}")
        return
    KanbanApp().run()


if __name__ == "__main__":
    run()
