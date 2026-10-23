from __future__ import annotations

from .models import ServiceClass, Status, Task

GLOBAL_WIP_LIMIT = 1


def global_doing_count(
    tasks: list[Task],
    excluding_id: str | None = None,
    visible_names: "set[str] | list[str] | None" = None,
) -> int:
    """Tareas en progreso fuera de Urgencias (el WIP global del tablero).

    `visible_names`, cuando se pasa, restringe el conteo a objetivos que
    siguen como carril en el tablero (activos + apagados). Sin él se
    contarían también tareas "en progreso" que quedaron huérfanas bajo un
    objetivo ya cerrado/archivado — invisibles en el tablero pero que
    seguirían bloqueando el WIP para siempre.
    """
    names = set(visible_names) if visible_names is not None else None
    return sum(
        1
        for t in tasks
        if t.service_class != ServiceClass.EXPEDITE
        and t.status == Status.DOING
        and t.id != excluding_id
        and (names is None or t.objective in names)
    )


def intangible_debt(tasks: list[Task]) -> int:
    """Cuántas tareas Intangibles "se deben" en total, a ojo de 1 por cada
    tarea Estándar/Fecha fija/Expedito ya terminada, descontando las
    Intangibles que ya se hicieron.

    Puramente informativo: no bloquea nada, solo indica una deuda
    acumulada a partir de todo lo que ya está en Hecho.
    """
    done = [t for t in tasks if t.status == Status.DONE]
    non_intangible_done = sum(1 for t in done if t.service_class != ServiceClass.INTANGIBLE)
    intangible_done = sum(1 for t in done if t.service_class == ServiceClass.INTANGIBLE)
    return max(0, non_intangible_done - intangible_done)
