"""Temas propios de la app, registrados en Textual con `App.register_theme`.

Una vez registrados se comportan como cualquier tema de Textual: aparecen
en la paleta de comandos (`ctrl+p` → cambiar tema) y todo el estilo de la
app (kanban.tcss) los usa a través de sus variables ($primary, $accent...).
"""

from __future__ import annotations

from textual.theme import Theme

# Alto contraste en blanco y negro puros: ningún color, solo negro, blanco
# y grises. Las alertas se distinguen por el tipo de borde (ver kanban.tcss)
# y la frescura de cada carril con un medidor de bloques en su título.
KANBAN_HIGH_CONTRAST = Theme(
    name="kanban-high-contrast",
    primary="#ffffff",
    secondary="#ffffff",
    accent="#ffffff",
    warning="#ffffff",
    error="#ffffff",
    success="#ffffff",
    foreground="#ffffff",
    background="#000000",
    surface="#000000",
    panel="#1c1c1c",
    boost="#262626",
    dark=True,
    # Texto atenuado menos atenuado que en los temas normales.
    text_alpha=1.0,
    luminosity_spread=0.0,
    variables={
        "text-muted": "#d0d0d0",
        "border": "#ffffff",
        "border-blurred": "#9e9e9e",
        "block-cursor-background": "#ffffff",
        "block-cursor-foreground": "#000000",
        "block-cursor-text-style": "bold",
        "input-cursor-background": "#ffffff",
        "input-cursor-foreground": "#000000",
        "input-selection-background": "#ffffff 35%",
        "screen-selection-background": "#ffffff 35%",
        "footer-background": "#000000",
        "footer-foreground": "#ffffff",
        "footer-key-foreground": "#ffffff",
        "footer-description-foreground": "#ffffff",
        "scrollbar": "#bcbcbc",
        "scrollbar-hover": "#ffffff",
        "scrollbar-active": "#ffffff",
        "scrollbar-background": "#000000",
        "scrollbar-background-hover": "#1c1c1c",
        "scrollbar-background-active": "#1c1c1c",
        "scrollbar-corner-color": "#000000",
    },
)

CUSTOM_THEMES = [KANBAN_HIGH_CONTRAST]
