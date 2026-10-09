from __future__ import annotations

import zlib

_PALETTE = [
    "#f87171",
    "#fb923c",
    "#fbbf24",
    "#a3e635",
    "#34d399",
    "#22d3ee",
    "#60a5fa",
    "#a78bfa",
    "#f472b6",
    "#94a3b8",
]


def label_color(label: str) -> str:
    idx = zlib.crc32(label.encode("utf-8")) % len(_PALETTE)
    return _PALETTE[idx]


def priority_color(priority: int) -> str:
    if priority <= 1:
        return "#f87171"
    if priority <= 3:
        return "#fbbf24"
    return "#34d399"
