from __future__ import annotations

from pathlib import Path

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from .. import storage
from ..models import Status, Task
from ..settings import load_settings
from ..widgets.task_card import SERVICE_CLASS_ICON

STATUS_LABELS = {
    Status.BACKLOG: "Pendiente",
    Status.DOING: "En progreso",
    Status.DONE: "Hecho",
}


class TaskDetailScreen(ModalScreen[bool]):
    """Vista de solo lectura de una tarea, con su descripción, criterio de
    aceptación completos y sus comentarios — y un cuadro para añadir uno
    nuevo, sin entrar al formulario de edición."""

    def __init__(self, task: Task, tasks_dir: Path) -> None:
        super().__init__()
        self.task_item = task
        self.tasks_dir = tasks_dir
        self.changed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-dialog"):
            yield Static(self._header(), id="detail-title")
            yield VerticalScroll(id="detail-body")
            with Horizontal(classes="form-row"):
                yield Input(placeholder="Añadir comentario…", id="detail-comment-input")
                yield Button("Comentar", id="detail-comment-btn", variant="success")
            with Horizontal(id="detail-actions"):
                yield Button("Cerrar", id="detail-done", variant="default")

    def _header(self) -> str:
        task = self.task_item
        icon = SERVICE_CLASS_ICON[task.service_class]
        bits = [f"{icon} [bold]{escape(task.title)}[/bold]", STATUS_LABELS[task.status], f"P{task.priority}"]
        if task.objective:
            bits.append(f"obj: {escape(task.objective)}")
        if task.due_date:
            bits.append(f"vence {task.due_date.isoformat()}")
        if task.labels:
            bits.append(", ".join(task.labels))
        return "   ·   ".join(bits)

    def on_mount(self) -> None:
        self._render_body()
        self.query_one("#detail-comment-input", Input).focus()

    def _render_body(self) -> None:
        body = self.query_one("#detail-body", VerticalScroll)
        body.remove_children()

        if self.task_item.blocked_by:
            all_tasks = storage.load_all_tasks(self.tasks_dir)
            blocker = next((t for t in all_tasks if t.id == self.task_item.blocked_by), None)
            if blocker is not None and blocker.status != Status.DONE:
                body.mount(
                    Static(
                        f"[bold #ff6b6b]🔒 Bloqueada por «{escape(blocker.title)}»[/] "
                        f"({STATUS_LABELS[blocker.status]})",
                        classes="detail-block",
                    )
                )

        stuck_doing_days = load_settings(self.tasks_dir).stuck_doing_days
        if self.task_item.is_stuck_doing(stuck_doing_days):
            body.mount(
                Static("[bold #b36bff]⏳ Lleva demasiados días en progreso[/]", classes="detail-block")
            )

        description = escape(self.task_item.description) or "(sin resumen)"
        acceptance = escape(self.task_item.acceptance_criteria) or "(sin criterio de aceptación)"
        body.mount(Static(f"[bold]Resumen[/bold]\n{description}", classes="detail-block"))
        body.mount(Static(f"[bold]Criterio de aceptación[/bold]\n{acceptance}", classes="detail-block"))
        body.mount(Static("[bold]Comentarios[/bold]", classes="detail-block"))
        if not self.task_item.comments:
            body.mount(Static("(sin comentarios)", classes="empty-hint"))
        else:
            for comment in sorted(self.task_item.comments, key=lambda c: c.timestamp, reverse=True):
                ts = comment.timestamp.strftime("%Y-%m-%d %H:%M")
                body.mount(Static(f"[dim]{ts}[/dim]  {escape(comment.text)}", classes="detail-comment"))

    @on(Button.Pressed, "#detail-comment-btn")
    @on(Input.Submitted, "#detail-comment-input")
    def add_comment(self) -> None:
        field = self.query_one("#detail-comment-input", Input)
        text = field.value.strip()
        if not text:
            return
        self.task_item.add_comment(text)
        storage.save_task(self.tasks_dir, self.task_item)
        self.changed = True
        field.value = ""
        self._render_body()
        field.focus()

    @on(Button.Pressed, "#detail-done")
    def done(self) -> None:
        self.dismiss(self.changed)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(self.changed)
