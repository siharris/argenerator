"""Geometry: maps a validated Roadmap onto EMU coordinates for the PPTX renderer.

Nothing about layout geometry is authored in the YAML (e.g. the per-domain fork/branch
point) -- it is entirely derived here from the domain/track/event structure.
"""

from __future__ import annotations

from dataclasses import dataclass

from pptx.util import Inches

from argenerator.period import period_at_index, period_index, total_quarters
from argenerator.schema import Dependency, Domain, Event, Roadmap, TimelineConfig


class LayoutError(ValueError):
    pass


@dataclass
class Geometry:
    slide_width: int = Inches(13.333)
    slide_height: int = Inches(7.5)
    left_margin: int = Inches(0.4)
    right_margin: int = Inches(0.3)
    top_margin: int = Inches(0.55)
    title_height: int = Inches(0.5)
    header_height: int = Inches(0.5)
    footer_height: int = Inches(0.35)
    badge_width: int = Inches(1.9)
    fork_gap: int = Inches(0.15)
    connector_len: int = Inches(0.25)
    track_height: int = Inches(0.5)
    domain_padding: int = Inches(0.12)


@dataclass
class ColumnLayout:
    timeline: TimelineConfig
    start_x: int
    end_x: int
    col_width: float
    total_quarters: int

    def x_for_period(self, period: str, position_in_quarter: float = 0.5) -> int:
        idx = period_index(
            period, self.timeline.start, self.timeline.fiscal_year_prefix, self.timeline.quarters_per_year
        )
        return round(self.start_x + (idx + position_in_quarter) * self.col_width)

    def column_bounds(self, index: int) -> tuple[int, int]:
        return (
            round(self.start_x + index * self.col_width),
            round(self.start_x + (index + 1) * self.col_width),
        )


@dataclass
class QuarterHeaderCell:
    label: str
    x0: int
    x1: int


@dataclass
class FiscalYearHeaderGroup:
    label: str
    x0: int
    x1: int
    quarters: list[QuarterHeaderCell]


@dataclass
class DomainLayout:
    domain: Domain
    top: int
    height: int
    badge_x: int
    badge_width: int
    branch_x: int
    branch_y: int
    track_ys: list[int]  # aligned with domain.tracks


@dataclass
class EventPosition:
    domain: Domain
    track_id: str
    event: Event
    x: int
    y: int
    label_position: str  # "above" | "below"

    @property
    def key(self) -> str:
        return f"{self.domain.id}.{self.track_id}.{self.event.id}"


@dataclass
class DependencyLayout:
    dependency: Dependency
    start: EventPosition
    end: EventPosition
    # True when `start` is the chronologically last event on its track: the source
    # track's line stops there instead of continuing to the timeline's right edge,
    # and the dependency renders as a solid merge into the target rather than a
    # dashed annotation arrow.
    terminates_source: bool = False


@dataclass
class RoadmapLayout:
    roadmap: Roadmap
    geometry: Geometry
    columns: ColumnLayout
    fiscal_year_groups: list[FiscalYearHeaderGroup]
    domain_layouts: list[DomainLayout]
    event_positions: list[EventPosition]
    event_index: dict[str, EventPosition]
    dependency_layouts: list[DependencyLayout]
    track_line_ends: dict[str, int]  # "domain_id.track_id" -> x where the track's line stops


def timeline_x_bounds(geom: Geometry) -> tuple[int, int]:
    start_x = geom.left_margin + geom.badge_width + geom.fork_gap + geom.connector_len
    end_x = geom.slide_width - geom.right_margin
    return start_x, end_x


def compute_column_layout(timeline: TimelineConfig, geom: Geometry) -> ColumnLayout:
    total_q = total_quarters(timeline.start, timeline.end, timeline.fiscal_year_prefix, timeline.quarters_per_year)
    start_x, end_x = timeline_x_bounds(geom)
    col_width = (end_x - start_x) / total_q
    return ColumnLayout(timeline=timeline, start_x=start_x, end_x=end_x, col_width=col_width, total_quarters=total_q)


def compute_fiscal_year_groups(columns: ColumnLayout) -> list[FiscalYearHeaderGroup]:
    timeline = columns.timeline
    groups: list[FiscalYearHeaderGroup] = []
    current_year: int | None = None
    current_quarters: list[QuarterHeaderCell] = []

    def flush() -> None:
        if current_quarters:
            groups.append(
                FiscalYearHeaderGroup(
                    label=f"{timeline.fiscal_year_prefix}{current_year}",
                    x0=current_quarters[0].x0,
                    x1=current_quarters[-1].x1,
                    quarters=list(current_quarters),
                )
            )

    for index in range(columns.total_quarters):
        year, quarter = period_at_index(
            timeline.start, index, timeline.fiscal_year_prefix, timeline.quarters_per_year
        )
        if year != current_year:
            flush()
            current_year = year
            current_quarters = []
        x0, x1 = columns.column_bounds(index)
        current_quarters.append(QuarterHeaderCell(label=f"Q{quarter}", x0=x0, x1=x1))
    flush()
    return groups


def compute_vertical_layout(domains: list[Domain], geom: Geometry) -> list[DomainLayout]:
    available_height = geom.slide_height - geom.top_margin - geom.title_height - geom.header_height - geom.footer_height
    required_height = sum(
        len(domain.tracks) * geom.track_height + 2 * geom.domain_padding for domain in domains
    )
    scale = 1.0 if required_height <= 0 else min(1.0, available_height / required_height)

    track_height = geom.track_height * scale
    domain_padding = geom.domain_padding * scale

    branch_x = geom.left_margin + geom.badge_width + geom.fork_gap
    y_cursor = geom.top_margin + geom.title_height + geom.header_height

    layouts: list[DomainLayout] = []
    for domain in domains:
        n_tracks = max(len(domain.tracks), 1)
        domain_height = round(n_tracks * track_height + 2 * domain_padding)
        domain_top = round(y_cursor)
        track_ys = [
            round(domain_top + domain_padding + (i + 0.5) * track_height) for i in range(len(domain.tracks))
        ]
        branch_y = round((min(track_ys) + max(track_ys)) / 2) if track_ys else domain_top + domain_height // 2
        layouts.append(
            DomainLayout(
                domain=domain,
                top=domain_top,
                height=domain_height,
                badge_x=geom.left_margin,
                badge_width=geom.badge_width,
                branch_x=branch_x,
                branch_y=branch_y,
                track_ys=track_ys,
            )
        )
        y_cursor += domain_height
    return layouts


def compute_event_positions(columns: ColumnLayout, domain_layouts: list[DomainLayout]) -> list[EventPosition]:
    positions: list[EventPosition] = []
    for domain_layout in domain_layouts:
        for track_index, track in enumerate(domain_layout.domain.tracks):
            track_y = domain_layout.track_ys[track_index]
            for event in track.events:
                # The reference roadmap always labels above the line; only deviate
                # when a caller explicitly overrides it for a same-track collision.
                label_position = event.label_position or "above"
                x = columns.x_for_period(event.period, event.position_in_quarter)
                positions.append(
                    EventPosition(
                        domain=domain_layout.domain,
                        track_id=track.id,
                        event=event,
                        x=x,
                        y=track_y,
                        label_position=label_position,
                    )
                )
    return positions


def resolve_dependencies(
    dependencies: list[Dependency],
    event_index: dict[str, EventPosition],
) -> list[DependencyLayout]:
    resolved: list[DependencyLayout] = []
    for dep in dependencies:
        start = event_index.get(dep.from_event)
        end = event_index.get(dep.to_event)
        if start is None:
            raise LayoutError(f"Dependency references unknown from_event '{dep.from_event}'")
        if end is None:
            raise LayoutError(f"Dependency references unknown to_event '{dep.to_event}'")
        resolved.append(
            DependencyLayout(dependency=dep, start=start, end=end, terminates_source=dep.style == "converge")
        )
    return resolved


def compute_track_line_ends(
    domain_layouts: list[DomainLayout],
    event_index: dict[str, EventPosition],
    dependency_layouts: list[DependencyLayout],
    default_end_x: int,
) -> dict[str, int]:
    """Map "domain_id.track_id" -> x where that track's horizontal line stops.

    A track stops early -- instead of running to the timeline's right edge -- only
    when the DSL says so explicitly: either an `end`-type event on the track, or a
    `converge`-style dependency sourced from it. Stopping and converging are
    independent: a track can stop on its own with no dependency at all.
    """
    ends: dict[str, int] = {}
    for domain_layout in domain_layouts:
        for track in domain_layout.domain.tracks:
            key = f"{domain_layout.domain.id}.{track.id}"
            ends[key] = default_end_x
            for event in track.events:
                if event.type == "end":
                    pos = event_index[f"{key}.{event.id}"]
                    ends[key] = min(ends[key], pos.x)
    for dep_layout in dependency_layouts:
        if dep_layout.terminates_source:
            key = f"{dep_layout.start.domain.id}.{dep_layout.start.track_id}"
            ends[key] = min(ends.get(key, default_end_x), dep_layout.start.x)
    return ends


def compute_layout(roadmap: Roadmap, geom: Geometry | None = None) -> RoadmapLayout:
    geom = geom or Geometry()
    columns = compute_column_layout(roadmap.timeline, geom)
    fiscal_year_groups = compute_fiscal_year_groups(columns)
    domain_layouts = compute_vertical_layout(roadmap.domains, geom)
    event_positions = compute_event_positions(columns, domain_layouts)
    event_index = {pos.key: pos for pos in event_positions}
    dependency_layouts = resolve_dependencies(roadmap.dependencies, event_index)
    track_line_ends = compute_track_line_ends(domain_layouts, event_index, dependency_layouts, columns.end_x)
    return RoadmapLayout(
        roadmap=roadmap,
        geometry=geom,
        columns=columns,
        fiscal_year_groups=fiscal_year_groups,
        domain_layouts=domain_layouts,
        event_positions=event_positions,
        event_index=event_index,
        dependency_layouts=dependency_layouts,
        track_line_ends=track_line_ends,
    )
