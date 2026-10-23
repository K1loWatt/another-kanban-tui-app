from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from .. import storage
from ..models import ServiceClass, Status, Task
from ..objectives import LANE_WIP_LIMIT, active_objectives, load_objectives

BAR_WIDTH = 24

SERVICE_CLASS_LABELS = {
    ServiceClass.STANDARD: "Estándar",
    ServiceClass.FIXED_DATE: "Fecha fija",
    ServiceClass.EXPEDITE: "Expedito",
    ServiceClass.INTANGIBLE: "Intangible",
}

SERVICE_CLASS_COLOR = {
    ServiceClass.STANDARD: "#c9a06a",
    ServiceClass.FIXED_DATE: "#ffcc66",
    ServiceClass.EXPEDITE: "#ff5f56",
    ServiceClass.INTANGIBLE: "#d9b36c",
}


def _bar(value: int, max_value: int, color: str, width: int = BAR_WIDTH) -> str:
    if max_value <= 0:
        filled = 0
    else:
        filled = round((value / max_value) * width)
    filled = max(0, min(width, filled))
    bar = "█" * filled + "░" * (width - filled)
    return f"[{color}]{bar}[/{color}] {value}"


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


class MetricsScreen(ModalScreen[None]):
    """Pantalla de solo lectura con métricas kanban del tablero."""

    def __init__(self, tasks_dir: Path) -> None:
        super().__init__()
        self.tasks_dir = tasks_dir

    def compose(self) -> ComposeResult:
        with Vertical(id="metrics-dialog"):
            yield Static("Métricas del tablero", id="metrics-title")
            yield VerticalScroll(id="metrics-body")
            with Horizontal(id="metrics-actions"):
                yield Button("Cerrar", id="metrics-done", variant="default")

    def on_mount(self) -> None:
        tasks = storage.load_all_tasks(self.tasks_dir)
        objectives = sorted(
            active_objectives(load_objectives(self.tasks_dir)), key=lambda o: (o.priority, o.created_at)
        )
        body = self.query_one("#metrics-body", VerticalScroll)

        body.mount(Static("Throughput — tareas completadas por semana (últimas 8)", classes="metrics-section"))
        for label, count, max_count in self._weekly_throughput(tasks):
            body.mount(Static(f"{label}  {_bar(count, max_count, '#6bbf6b')}", classes="metrics-row"))

        body.mount(Static("", classes="metrics-spacer"))
        body.mount(Static("Tiempos medios (tareas terminadas)", classes="metrics-section"))
        lead, cycle = self._lead_and_cycle_time(tasks)
        lead_text = f"{lead:.1f} días" if lead is not None else "sin datos"
        cycle_text = f"{cycle:.1f} días" if cycle is not None else "sin datos"
        body.mount(Static(f"Lead time medio (creación → hecho): {lead_text}", classes="metrics-row"))
        body.mount(Static(f"Cycle time medio (en progreso → hecho): {cycle_text}", classes="metrics-row"))

        body.mount(Static("", classes="metrics-spacer"))
        body.mount(Static(f"WIP actual por carril (límite {LANE_WIP_LIMIT})", classes="metrics-section"))
        if not objectives:
            body.mount(Static("Sin carriles activos.", classes="metrics-row"))
        for objective in objectives:
            doing = sum(1 for t in tasks if t.objective == objective.name and t.status == Status.DOING)
            at_limit = " ⚠ en el límite" if doing >= LANE_WIP_LIMIT else ""
            body.mount(
                Static(
                    f"{objective.name}: {_bar(doing, max(LANE_WIP_LIMIT, 1), '#ffb454')}{at_limit}",
                    classes="metrics-row",
                )
            )

        body.mount(Static("", classes="metrics-spacer"))
        body.mount(Static("Tareas activas por clase de servicio", classes="metrics-section"))
        active_tasks = [t for t in tasks if t.status != Status.DONE]
        counts = {sc: sum(1 for t in active_tasks if t.service_class == sc) for sc in ServiceClass}
        max_count = max(counts.values(), default=0)
        for service_class, count in counts.items():
            color = SERVICE_CLASS_COLOR[service_class]
            body.mount(
                Static(
                    f"{SERVICE_CLASS_LABELS[service_class]:<12} {_bar(count, max_count, color)}",
                    classes="metrics-row",
                )
            )

    @staticmethod
    def _weekly_throughput(tasks: list[Task]) -> list[tuple[str, int, int]]:
        today = date.today()
        current_week_start = _week_start(today)
        weeks = [current_week_start - timedelta(weeks=i) for i in range(7, -1, -1)]
        counts = []
        for week_start in weeks:
            week_end = week_start + timedelta(days=6)
            count = sum(
                1
                for t in tasks
                if t.completed_at and week_start <= t.completed_at <= week_end
            )
            counts.append(count)
        max_count = max(counts, default=0)
        labels = [w.strftime("%d/%m") for w in weeks]
        return [(label, count, max_count) for label, count in zip(labels, counts)]

    @staticmethod
    def _lead_and_cycle_time(tasks: list[Task]) -> tuple[float | None, float | None]:
        lead_samples = []
        cycle_samples = []
        for task in tasks:
            if task.status != Status.DONE or not task.completed_at:
                continue
            created = task.created_at.date()
            lead_samples.append((task.completed_at - created).days)
            if task.started_at:
                cycle_samples.append((task.completed_at - task.started_at).days)
        lead_avg = sum(lead_samples) / len(lead_samples) if lead_samples else None
        cycle_avg = sum(cycle_samples) / len(cycle_samples) if cycle_samples else None
        return lead_avg, cycle_avg

    @on(Button.Pressed, "#metrics-done")
    def done(self) -> None:
        self.dismiss(None)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(None)
