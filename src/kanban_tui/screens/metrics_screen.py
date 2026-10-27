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
from ..objectives import active_objectives, load_objectives, visible_objectives
from ..settings import load_settings
from ..wip_rules import global_doing_count, intangible_state

BAR_WIDTH = 24
DAILY_THROUGHPUT_DAYS = 14

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
        settings = load_settings(self.tasks_dir)
        objectives = sorted(
            active_objectives(load_objectives(self.tasks_dir)), key=lambda o: (o.priority, o.created_at)
        )
        active_names = [o.name for o in objectives]
        visible_names = [o.name for o in visible_objectives(load_objectives(self.tasks_dir))]
        body = self.query_one("#metrics-body", VerticalScroll)

        body.mount(
            Static(
                f"Throughput — tareas completadas por día (últimos {DAILY_THROUGHPUT_DAYS} días)",
                classes="metrics-section",
            )
        )
        for label, count, max_count in self._daily_throughput(tasks):
            body.mount(Static(f"{label}  {_bar(count, max_count, '#6bbf6b')}", classes="metrics-row"))

        body.mount(Static("", classes="metrics-spacer"))
        body.mount(Static("Tiempos medios (tareas terminadas)", classes="metrics-section"))
        lead, cycle = self._lead_and_cycle_time(tasks)
        lead_text = f"{lead:.1f} días" if lead is not None else "sin datos"
        cycle_text = f"{cycle:.1f} días" if cycle is not None else "sin datos"
        body.mount(Static(f"Lead time medio (creación → hecho): {lead_text}", classes="metrics-row"))
        body.mount(Static(f"Cycle time medio (en progreso → hecho): {cycle_text}", classes="metrics-row"))

        body.mount(Static("", classes="metrics-spacer"))
        body.mount(Static("WIP actual", classes="metrics-section"))
        doing_global = global_doing_count(tasks, visible_names=visible_names)
        body.mount(
            Static(
                f"Objetivos (límite global {settings.global_wip_limit}): "
                f"{_bar(doing_global, max(settings.global_wip_limit, 1), '#ffb454')}",
                classes="metrics-row",
            )
        )
        doing_urgent = sum(
            1 for t in tasks if t.service_class == ServiceClass.EXPEDITE and t.status == Status.DOING
        )
        body.mount(
            Static(
                f"Urgencias (límite {settings.expedite_doing_limit}): "
                f"{_bar(doing_urgent, max(settings.expedite_doing_limit, 1), '#ff5f56')}",
                classes="metrics-row",
            )
        )

        body.mount(Static("", classes="metrics-spacer"))
        body.mount(
            Static(
                f"Cadencia de intangibles (toca cada {settings.intangible_cadence} tareas)",
                classes="metrics-section",
            )
        )
        if not objectives:
            body.mount(Static("Sin objetivos activos.", classes="metrics-row"))
        else:
            intangible_streaks, needs_intangible = intangible_state(
                tasks, active_names, settings.intangible_cadence
            )
            for objective in objectives:
                name = objective.name
                intangible_badge = " 💡 toca intangible" if name in needs_intangible else ""
                body.mount(
                    Static(
                        f"{name}: racha estándar/fecha fija {intangible_streaks.get(name, 0)}/"
                        f"{settings.intangible_cadence}{intangible_badge}",
                        classes="metrics-row",
                    )
                )

        body.mount(Static("", classes="metrics-spacer"))
        body.mount(Static("Bloqueos y tareas atascadas", classes="metrics-section"))
        blocked_count = sum(
            1
            for t in tasks
            if t.blocked_by
            and t.status != Status.DONE
            and any(other.id == t.blocked_by and other.status != Status.DONE for other in tasks)
        )
        stuck_count = sum(1 for t in tasks if t.is_stuck_doing(settings.stuck_doing_days))
        body.mount(Static(f"Tareas bloqueadas por otra: {blocked_count}", classes="metrics-row"))
        body.mount(Static(f"Tareas atascadas en progreso: {stuck_count}", classes="metrics-row"))

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
    def _daily_throughput(tasks: list[Task]) -> list[tuple[str, int, int]]:
        today = date.today()
        days = [today - timedelta(days=i) for i in range(DAILY_THROUGHPUT_DAYS - 1, -1, -1)]
        counts = [sum(1 for t in tasks if t.completed_at == day) for day in days]
        max_count = max(counts, default=0)
        labels = [d.strftime("%d/%m") for d in days]
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
