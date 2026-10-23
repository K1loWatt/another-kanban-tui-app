from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from re import sub as re_sub

import yaml


class Status(str, Enum):
    BACKLOG = "backlog"
    DOING = "doing"
    DONE = "done"


class ServiceClass(str, Enum):
    STANDARD = "standard"
    FIXED_DATE = "fixed_date"
    EXPEDITE = "expedite"
    INTANGIBLE = "intangible"


_LEGACY_TYPE_TO_SERVICE_CLASS = {
    "normal": ServiceClass.STANDARD,
    "deadline": ServiceClass.FIXED_DATE,
    "urgent": ServiceClass.EXPEDITE,
}

PRIORITY_MIN = 0
PRIORITY_MAX = 5
PRIORITY_DEFAULT = 3

APPROACHING_DAYS = 3
STALE_INTANGIBLE_DAYS = 30

ACCEPTANCE_CRITERIA_MARKER = "## Criterio de aceptación"

_LEGACY_PRIORITY = {
    "low": 5,
    "baja": 5,
    "medium": 3,
    "media": 3,
    "high": 0,
    "alta": 0,
}


def _parse_priority(value) -> int:
    if value is None or value == "":
        return PRIORITY_DEFAULT
    if isinstance(value, bool):
        return PRIORITY_DEFAULT
    if isinstance(value, int):
        return max(PRIORITY_MIN, min(PRIORITY_MAX, value))
    text = str(value).strip().lower()
    if text in _LEGACY_PRIORITY:
        return _LEGACY_PRIORITY[text]
    try:
        return max(PRIORITY_MIN, min(PRIORITY_MAX, int(text)))
    except ValueError:
        return PRIORITY_DEFAULT


def _parse_service_class(meta: dict) -> ServiceClass:
    raw = meta.get("service_class")
    if raw:
        try:
            return ServiceClass(str(raw))
        except ValueError:
            pass
    legacy = meta.get("type")
    if legacy in _LEGACY_TYPE_TO_SERVICE_CLASS:
        return _LEGACY_TYPE_TO_SERVICE_CLASS[legacy]
    return ServiceClass.STANDARD


def oneline(text: str, max_len: int = 90) -> str:
    """Collapse a free-form text block into a single truncated line for compact rows."""
    collapsed = " ".join(text.split())
    if len(collapsed) > max_len:
        return collapsed[: max_len - 1].rstrip() + "…"
    return collapsed


def _slugify(text: str) -> str:
    text = text.strip().lower()
    text = re_sub(r"[^a-z0-9]+", "-", text)
    return re_sub(r"-{2,}", "-", text).strip("-") or "task"


def _parse_date(value) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _parse_datetime(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if value:
        return datetime.fromisoformat(str(value))
    return datetime.now()


@dataclass
class Task:
    title: str
    status: Status = Status.BACKLOG
    service_class: ServiceClass = ServiceClass.STANDARD
    objective: str = ""
    priority: int = PRIORITY_DEFAULT
    labels: list[str] = field(default_factory=list)
    due_date: date | None = None
    started_at: date | None = None
    completed_at: date | None = None
    description: str = ""
    acceptance_criteria: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    path: Path | None = field(default=None, compare=False, repr=False)

    @classmethod
    def from_markdown(cls, text: str, path: Path | None = None) -> "Task":
        meta, body = cls._split_frontmatter(text)
        description, acceptance_criteria = cls._split_body(body)
        return cls(
            title=str(meta.get("title") or (path.stem if path else "Untitled")),
            status=Status(meta.get("status", "backlog")),
            service_class=_parse_service_class(meta),
            objective=str(meta.get("objective") or ""),
            priority=_parse_priority(meta.get("priority")),
            labels=list(meta.get("labels") or []),
            due_date=_parse_date(meta.get("due_date")),
            started_at=_parse_date(meta.get("started_at")),
            completed_at=_parse_date(meta.get("completed_at")),
            description=description,
            acceptance_criteria=acceptance_criteria,
            id=str(meta.get("id") or uuid.uuid4().hex[:8]),
            created_at=_parse_datetime(meta.get("created_at")),
            updated_at=_parse_datetime(meta.get("updated_at")),
            path=path,
        )

    @staticmethod
    def _split_frontmatter(text: str) -> tuple[dict, str]:
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                meta = yaml.safe_load(parts[1]) or {}
                body = parts[2]
                return meta, body
        return {}, text

    @staticmethod
    def _split_body(body: str) -> tuple[str, str]:
        text = body.strip("\n")
        marker_idx = text.find(ACCEPTANCE_CRITERIA_MARKER)
        if marker_idx == -1:
            return text.strip(), ""
        description = text[:marker_idx].strip()
        acceptance_criteria = text[marker_idx + len(ACCEPTANCE_CRITERIA_MARKER) :].strip()
        return description, acceptance_criteria

    def to_markdown(self) -> str:
        meta = {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "service_class": self.service_class.value,
            "objective": self.objective,
            "priority": self.priority,
            "labels": self.labels,
            "due_date": self.due_date,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        front = yaml.safe_dump(meta, sort_keys=False, default_flow_style=False, allow_unicode=True)
        body_parts = [self.description.strip()]
        if self.acceptance_criteria.strip():
            body_parts.append(f"{ACCEPTANCE_CRITERIA_MARKER}\n\n{self.acceptance_criteria.strip()}")
        body = "\n\n".join(part for part in body_parts if part)
        return f"---\n{front}---\n\n{body}\n"

    def filename(self) -> str:
        return f"{_slugify(self.title)}-{self.id}.md"

    @property
    def is_overdue(self) -> bool:
        return bool(self.due_date and self.due_date < date.today() and self.status != Status.DONE)

    @property
    def is_approaching(self) -> bool:
        if not self.due_date or self.status == Status.DONE:
            return False
        days_left = (self.due_date - date.today()).days
        return 0 <= days_left <= APPROACHING_DAYS

    @property
    def is_stale_intangible(self) -> bool:
        if self.service_class != ServiceClass.INTANGIBLE or self.status == Status.DONE:
            return False
        reference = self.updated_at.date() if isinstance(self.updated_at, datetime) else self.updated_at
        return (date.today() - reference).days > STALE_INTANGIBLE_DAYS
