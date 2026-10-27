from __future__ import annotations

from .models import ServiceClass, Status, Task

GLOBAL_WIP_LIMIT = 1

_INTANGIBLE_COUNTED = (ServiceClass.STANDARD, ServiceClass.FIXED_DATE)


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


def intangible_state(
    tasks: list[Task], active_names: list[str], cadence: int
) -> tuple[dict[str, int], set[str]]:
    """Racha de tareas Estándar/Fecha fija y objetivos a los que toca una
    Intangible antes de poder seguir con Estándar/Fecha fija.

    Si el objetivo no tiene ninguna tarea Intangible disponible (ni en
    Pendientes ni En progreso), no se exige nada — no tiene sentido
    bloquear a alguien por no hacer una tarea que no existe.
    """
    streaks: dict[str, int] = {name: 0 for name in active_names}
    required: set[str] = set()
    if cadence <= 0:
        return streaks, required

    for name in active_names:
        completions = sorted(
            (
                t
                for t in tasks
                if t.status == Status.DONE
                and t.objective == name
                and (
                    t.service_class in _INTANGIBLE_COUNTED
                    or t.service_class == ServiceClass.INTANGIBLE
                )
            ),
            key=lambda t: t.updated_at,
        )
        streak = 0
        for t in completions:
            streak = 0 if t.service_class == ServiceClass.INTANGIBLE else streak + 1
        streaks[name] = streak

        has_available_intangible = any(
            t.objective == name and t.service_class == ServiceClass.INTANGIBLE and t.status != Status.DONE
            for t in tasks
        )
        if streak >= cadence and has_available_intangible:
            required.add(name)
    return streaks, required
