from __future__ import annotations

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen[bool]):
    """A small Yes/No confirmation dialog."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Static(self.message, id="confirm-message")
            with Horizontal(id="confirm-actions"):
                yield Button("Cancelar", id="c-no", variant="default")
                yield Button("Eliminar", id="c-yes", variant="error")

    @on(Button.Pressed, "#c-no")
    def no(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#c-yes")
    def yes(self) -> None:
        self.dismiss(True)

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.dismiss(False)
