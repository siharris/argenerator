from argenerator.layout import (
    Geometry,
    compute_column_layout,
    compute_event_positions,
    compute_fiscal_year_groups,
    compute_layout,
    compute_vertical_layout,
    resolve_dependencies,
)
from argenerator.schema import Dependency, Domain, Event, Roadmap, Track, TimelineConfig


def make_timeline(start="FY27.Q1", end="FY27.Q4") -> TimelineConfig:
    return TimelineConfig(start=start, end=end)


def make_domain(name: str, track_names: list[str], n_events: int = 0) -> Domain:
    tracks = []
    for tname in track_names:
        events = [
            Event(type="milestone", period="FY27.Q1", label=f"{tname}-e{i}") for i in range(n_events)
        ]
        tracks.append(Track(name=tname, events=events))
    return Domain(name=name, tracks=tracks)


def test_column_layout_bounds_match_geometry_formula():
    geom = Geometry()
    timeline = make_timeline("FY27.Q1", "FY27.Q4")
    columns = compute_column_layout(timeline, geom)

    expected_start_x = geom.left_margin + geom.badge_width + geom.fork_gap + geom.connector_len
    expected_end_x = geom.slide_width - geom.right_margin

    assert columns.start_x == expected_start_x
    assert columns.end_x == expected_end_x
    assert columns.total_quarters == 4
    assert columns.col_width == (expected_end_x - expected_start_x) / 4


def test_x_for_period_matches_column_bounds():
    geom = Geometry()
    timeline = make_timeline("FY27.Q1", "FY27.Q4")
    columns = compute_column_layout(timeline, geom)

    x0, x1 = columns.column_bounds(2)  # FY27.Q3
    assert columns.x_for_period("FY27.Q3", 0.0) == x0
    assert columns.x_for_period("FY27.Q3", 1.0) == x1


def test_fiscal_year_groups_split_correctly_across_years():
    geom = Geometry()
    timeline = make_timeline("FY27.Q3", "FY28.Q2")  # 4 quarters spanning 2 fiscal years
    columns = compute_column_layout(timeline, geom)
    groups = compute_fiscal_year_groups(columns)

    assert [g.label for g in groups] == ["FY27", "FY28"]
    assert [q.label for q in groups[0].quarters] == ["Q3", "Q4"]
    assert [q.label for q in groups[1].quarters] == ["Q1", "Q2"]
    assert groups[0].x0 == columns.start_x
    assert groups[1].x1 == columns.end_x


def test_domains_do_not_overlap_vertically():
    geom = Geometry()
    domains = [make_domain("A", ["t1", "t2"]), make_domain("B", ["t1", "t2", "t3"])]
    layouts = compute_vertical_layout(domains, geom)

    assert layouts[0].top + layouts[0].height <= layouts[1].top
    for layout in layouts:
        assert all(layout.top <= y <= layout.top + layout.height for y in layout.track_ys)
        assert layout.track_ys == sorted(layout.track_ys)


def test_overflow_scaling_keeps_layout_within_available_height():
    geom = Geometry()
    # Many domains/tracks so the naive (unscaled) height would exceed the slide.
    domains = [make_domain(f"Domain{i}", [f"t{j}" for j in range(6)]) for i in range(10)]
    layouts = compute_vertical_layout(domains, geom)

    available_height = geom.slide_height - geom.top_margin - geom.title_height - geom.header_height - geom.footer_height
    total_used = sum(layout.height for layout in layouts)
    assert total_used <= available_height + 5  # small rounding tolerance in EMU
    # still non-overlapping even when scaled down
    for a, b in zip(layouts, layouts[1:]):
        assert a.top + a.height <= b.top


def test_event_positions_default_above_but_respect_override():
    geom = Geometry()
    track = Track(
        name="t1",
        events=[
            Event(type="milestone", period="FY27.Q1", label="e1"),
            Event(type="milestone", period="FY27.Q2", label="e2"),
            Event(type="milestone", period="FY27.Q3", label="e3", label_position="below"),
        ],
    )
    domain = Domain(name="D", tracks=[track])
    timeline = make_timeline()

    columns = compute_column_layout(timeline, geom)
    domain_layouts = compute_vertical_layout([domain], geom)
    positions = compute_event_positions(columns, domain_layouts)

    positions_sorted = sorted(positions, key=lambda p: p.x)
    assert [p.label_position for p in positions_sorted] == ["above", "above", "below"]


def _two_domain_roadmap(style: str, track_a_events: list[Event] | None = None) -> Roadmap:
    domain_a = Domain(
        id="a",
        name="A",
        tracks=[
            Track(
                id="t1",
                name="T1",
                events=track_a_events
                or [
                    Event(id="e1", type="start", period="FY27.Q1", label="start"),
                    Event(id="e2", type="delivery", period="FY27.Q2", label="last"),
                ],
            )
        ],
    )
    domain_b = Domain(
        id="b",
        name="B",
        tracks=[Track(id="t2", name="T2", events=[Event(id="e3", type="milestone", period="FY27.Q3", label="mid")])],
    )
    return Roadmap(
        timeline=make_timeline(),
        domains=[domain_a, domain_b],
        dependencies=[Dependency(from_event="a.t1.e2", to_event="b.t2.e3", style=style)],
    )


def test_converge_style_dependency_shortens_source_track_into_a_merge():
    layout = compute_layout(_two_domain_roadmap("converge"))

    dep_layout = layout.dependency_layouts[0]
    assert dep_layout.terminates_source is True
    assert layout.track_line_ends["a.t1"] == dep_layout.start.x
    assert layout.track_line_ends["a.t1"] < layout.columns.end_x
    assert layout.track_line_ends["b.t2"] == layout.columns.end_x


def test_non_converge_dependency_leaves_source_track_full_length():
    layout = compute_layout(_two_domain_roadmap("dashed"))

    assert layout.dependency_layouts[0].terminates_source is False
    assert layout.track_line_ends["a.t1"] == layout.columns.end_x


def test_end_event_stops_track_with_no_dependency_at_all():
    events = [
        Event(id="e1", type="start", period="FY27.Q1", label="start"),
        Event(id="e2", type="end", period="FY27.Q2", label="stop"),
    ]
    roadmap = _two_domain_roadmap("dashed", track_a_events=events)
    roadmap.dependencies = []  # stopping a track must not require a dependency
    layout = compute_layout(roadmap)

    stop_x = layout.event_index["a.t1.e2"].x
    assert layout.track_line_ends["a.t1"] == stop_x
    assert layout.track_line_ends["a.t1"] < layout.columns.end_x


def test_resolve_dependencies_raises_on_unknown_ref():
    import pytest
    from argenerator.layout import LayoutError

    dep = Dependency(from_event="a.b.c", to_event="d.e.f")
    with pytest.raises(LayoutError):
        resolve_dependencies([dep], {})
