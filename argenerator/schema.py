"""Pydantic schema for the roadmap YAML DSL, plus loading + cross-field validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from argenerator.period import PeriodError, parse_period, period_in_range

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_PERIOD_SHAPE_RE = re.compile(r"^[A-Za-z]+\d+\.Q\d+$")


def slugify(name: str) -> str:
    slug = _SLUG_RE.sub("_", name.strip().lower()).strip("_")
    return slug or "item"


class SchemaError(ValueError):
    pass


class TimelineConfig(BaseModel):
    start: str
    end: str
    fiscal_year_prefix: str = "FY"
    quarters_per_year: int = Field(default=4, ge=1)


class Event(BaseModel):
    id: str | None = None
    # "end" explicitly stops a track's line at this point (no marker, like "start") --
    # this is how a swim lane is stopped without converging into another track.
    type: Literal["milestone", "delivery", "start", "end"]
    period: str
    label: str
    highlight: bool = False
    label_position: Literal["above", "below"] | None = None
    position_in_quarter: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("period")
    @classmethod
    def _check_period_shape(cls, value: str) -> str:
        if not _PERIOD_SHAPE_RE.match(value.strip()):
            raise ValueError(
                f"Invalid period '{value}': expected shape '<prefix><year>.Q<quarter>', e.g. 'FY28.Q3'"
            )
        return value.strip()


class Track(BaseModel):
    id: str | None = None
    name: str
    events: list[Event] = Field(default_factory=list)


class Domain(BaseModel):
    id: str | None = None
    name: str
    icon: str | None = None
    tracks: list[Track]


class Dependency(BaseModel):
    from_event: str
    to_event: str
    # "converge" renders a solid curved merge into the target instead of a dashed
    # annotation arrow, and stops the source track's line at from_event instead of
    # continuing it to the timeline's right edge.
    style: Literal["arrow", "dashed", "converge"] = "arrow"
    label: str | None = None


class Roadmap(BaseModel):
    title: str = "Architecture Roadmap"
    timeline: TimelineConfig
    domains: list[Domain]
    dependencies: list[Dependency] = Field(default_factory=list)
    footer_link_text: str = "Link to Roadmap timeline"
    confidentiality_text: str = "Highly Confidential"
    theme: str | None = None
    icon_dir: str | None = None


def _assign_id(existing: set[str], preferred: str) -> str:
    if preferred not in existing:
        existing.add(preferred)
        return preferred
    n = 2
    while f"{preferred}_{n}" in existing:
        n += 1
    candidate = f"{preferred}_{n}"
    existing.add(candidate)
    return candidate


def _resolve_ids(roadmap: Roadmap) -> None:
    """Auto-generate missing ids (slugified from names) and disambiguate collisions,
    scoped so that "domain_id.track_id.event_id" dotted paths are unique."""
    domain_ids: set[str] = set()
    for domain in roadmap.domains:
        domain.id = _assign_id(domain_ids, domain.id or slugify(domain.name))
        track_ids: set[str] = set()
        for track in domain.tracks:
            track.id = _assign_id(track_ids, track.id or slugify(track.name))
            event_ids: set[str] = set()
            for event in track.events:
                preferred = event.id or slugify(event.label)
                event.id = _assign_id(event_ids, preferred)


def _validate_periods_in_range(roadmap: Roadmap) -> None:
    timeline = roadmap.timeline
    try:
        parse_period(timeline.start, timeline.fiscal_year_prefix)
        parse_period(timeline.end, timeline.fiscal_year_prefix)
    except PeriodError as exc:
        raise SchemaError(str(exc)) from exc

    for domain in roadmap.domains:
        for track in domain.tracks:
            for event in track.events:
                try:
                    in_range = period_in_range(
                        event.period,
                        timeline.start,
                        timeline.end,
                        timeline.fiscal_year_prefix,
                        timeline.quarters_per_year,
                    )
                except PeriodError as exc:
                    raise SchemaError(
                        f"Domain '{domain.name}' / track '{track.name}': {exc}"
                    ) from exc
                if not in_range:
                    raise SchemaError(
                        f"Domain '{domain.name}' / track '{track.name}': event '{event.label}' "
                        f"period '{event.period}' falls outside timeline "
                        f"[{timeline.start}, {timeline.end}]"
                    )


def _event_index(roadmap: Roadmap) -> dict[str, tuple]:
    """Map "domain_id.track_id.event_id" -> (domain, track, event)."""
    index: dict[str, tuple] = {}
    for domain in roadmap.domains:
        for track in domain.tracks:
            for event in track.events:
                index[f"{domain.id}.{track.id}.{event.id}"] = (domain, track, event)
    return index


def _validate_dependencies(roadmap: Roadmap) -> None:
    index = _event_index(roadmap)
    for dep in roadmap.dependencies:
        for ref, role in ((dep.from_event, "from_event"), (dep.to_event, "to_event")):
            if ref not in index:
                raise SchemaError(
                    f"Dependency {role} '{ref}' does not match any event "
                    f"(expected 'domain_id.track_id.event_id')"
                )


def load_roadmap(path: str | Path) -> Roadmap:
    path = Path(path)
    raw = yaml.safe_load(path.read_text())
    if raw is None:
        raise SchemaError(f"Roadmap file '{path}' is empty")
    roadmap = Roadmap.model_validate(raw)
    _resolve_ids(roadmap)
    _validate_periods_in_range(roadmap)
    _validate_dependencies(roadmap)
    return roadmap
