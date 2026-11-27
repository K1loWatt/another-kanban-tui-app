from __future__ import annotations

import zlib

# Solo variables del tema de Textual: los colores siguen al tema activo.
_PALETTE = [
    "$primary",
    "$secondary",
    "$accent",
    "$success",
    "$warning",
    "$error",
]


def label_color(label: str) -> str:
    idx = zlib.crc32(label.encode("utf-8")) % len(_PALETTE)
    return _PALETTE[idx]
