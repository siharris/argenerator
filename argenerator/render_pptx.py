"""Renders a computed RoadmapLayout to a .pptx file using python-pptx."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from argenerator.icons import resolve_icon, resolve_icon_dir
from argenerator.layout import DependencyLayout, DomainLayout, EventPosition, RoadmapLayout
from argenerator.theme import Theme, hex_to_rgbcolor

_MARKER_SIZE = Inches(0.09)
_LABEL_WIDTH = Inches(0.85)
_LABEL_HEIGHT = Inches(0.32)
_LABEL_GAP = Inches(0.03)
_HIGHLIGHT_HEIGHT = Inches(0.03)
_BADGE_ICON_SIZE = Inches(0.35)


def _set_fill(shape, hex_color: str | None) -> None:
    if hex_color is None:
        shape.fill.background()
        return
    shape.fill.solid()
    shape.fill.fore_color.rgb = hex_to_rgbcolor(hex_color)


def _set_line(shape, hex_color: str | None, width: Emu = Pt(1.25)) -> None:
    if hex_color is None:
        shape.line.fill.background()
        return
    shape.line.color.rgb = hex_to_rgbcolor(hex_color)
    shape.line.width = width


def _add_textbox(
    slide,
    x: int,
    y: int,
    width: int,
    height: int,
    text: str,
    theme_font,
    size: int,
    color: str,
    bold: bool = False,
    align: PP_ALIGN = PP_ALIGN.CENTER,
    anchor: MSO_ANCHOR = MSO_ANCHOR.MIDDLE,
):
    box = slide.shapes.add_textbox(x, y, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = theme_font.name
    run.font.color.rgb = hex_to_rgbcolor(color)
    return box


def _add_connector(
    slide, x0: int, y0: int, x1: int, y1: int, color: str, width: Emu, dashed: bool = False, curved: bool = False
):
    shape_type = MSO_CONNECTOR.CURVE if curved else MSO_CONNECTOR.STRAIGHT
    connector = slide.shapes.add_connector(shape_type, x0, y0, x1, y1)
    connector.line.color.rgb = hex_to_rgbcolor(color)
    connector.line.width = width
    if dashed:
        connector.line.dash_style = 2  # MSO_LINE_DASH_STYLE.DASH
    return connector


def _add_arrowhead(connector, end: str = "tail", arrow_type: str = "triangle") -> None:
    ln = connector.line._get_or_add_ln()
    tag = qn(f"a:{end}End")
    existing = ln.find(tag)
    if existing is not None:
        ln.remove(existing)
    element = ln.makeelement(tag, {"type": arrow_type})
    ln.append(element)


def _render_title(slide, layout: RoadmapLayout, theme: Theme) -> None:
    geom = layout.geometry
    _add_textbox(
        slide,
        geom.left_margin,
        geom.top_margin,
        geom.slide_width - geom.left_margin - geom.right_margin,
        geom.title_height,
        layout.roadmap.title,
        theme.font,
        theme.font.title_size,
        theme.title_color,
        bold=True,
        align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def _render_header(slide, layout: RoadmapLayout, theme: Theme) -> None:
    geom = layout.geometry
    header_top = geom.top_margin + geom.title_height
    # A timeline with one quarter per year (e.g. an annual/decade-scale roadmap) has
    # nothing meaningful to show in a second row, so give the year label the full
    # header height instead of drawing a redundant "Q1" row underneath it.
    single_row = layout.roadmap.timeline.quarters_per_year == 1
    fy_row_height = geom.header_height if single_row else geom.header_height // 2
    q_row_height = geom.header_height - fy_row_height

    for fy_group in layout.fiscal_year_groups:
        rect = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, fy_group.x0, header_top, fy_group.x1 - fy_group.x0, fy_row_height
        )
        _set_fill(rect, theme.header_fy_fill)
        _set_line(rect, theme.background_fill, Pt(0.75))
        rect.text_frame.margin_left = rect.text_frame.margin_right = 0
        rect.text_frame.margin_top = rect.text_frame.margin_bottom = 0
        rect.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = rect.text_frame.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        run = p.add_run()
        run.text = fy_group.label
        run.font.size = Pt(theme.font.header_size)
        run.font.bold = True
        run.font.name = theme.font.name
        run.font.color.rgb = hex_to_rgbcolor(theme.header_text)

        if single_row:
            continue

        for quarter in fy_group.quarters:
            q_rect = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, quarter.x0, header_top + fy_row_height, quarter.x1 - quarter.x0, q_row_height
            )
            _set_fill(q_rect, theme.header_q_fill)
            _set_line(q_rect, theme.background_fill, Pt(0.75))
            q_rect.text_frame.margin_left = q_rect.text_frame.margin_right = 0
            q_rect.text_frame.margin_top = q_rect.text_frame.margin_bottom = 0
            q_rect.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
            qp = q_rect.text_frame.paragraphs[0]
            qp.alignment = PP_ALIGN.CENTER
            qrun = qp.add_run()
            qrun.text = quarter.label
            qrun.font.size = Pt(theme.font.header_size - 1)
            qrun.font.name = theme.font.name
            qrun.font.color.rgb = hex_to_rgbcolor(theme.header_text)


def _render_domain_badge(slide, domain_layout: DomainLayout, theme: Theme, icons_dir) -> None:
    badge = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        domain_layout.badge_x,
        domain_layout.top,
        domain_layout.badge_width,
        domain_layout.height,
    )
    _set_fill(badge, theme.domain_badge_fill)
    _set_line(badge, None)
    badge.text_frame.word_wrap = True

    icon_path = resolve_icon(domain_layout.domain.icon, icons_dir)
    icon_x = domain_layout.badge_x + Inches(0.12)
    icon_y = domain_layout.top + domain_layout.height // 2 - _BADGE_ICON_SIZE // 2
    slide.shapes.add_picture(str(icon_path), icon_x, icon_y, width=_BADGE_ICON_SIZE, height=_BADGE_ICON_SIZE)

    text_x = icon_x + _BADGE_ICON_SIZE + Inches(0.08)
    text_width = domain_layout.badge_width - (text_x - domain_layout.badge_x) - Inches(0.08)
    _add_textbox(
        slide,
        text_x,
        domain_layout.top,
        max(text_width, Inches(0.3)),
        domain_layout.height,
        domain_layout.domain.name,
        theme.font,
        theme.font.domain_badge_size,
        theme.domain_badge_text,
        bold=True,
        align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def _render_domain_tracks(slide, layout: RoadmapLayout, domain_layout: DomainLayout, theme: Theme) -> None:
    geom = layout.geometry
    line_width = Pt(1.5)

    if domain_layout.track_ys:
        branch = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            domain_layout.branch_x - Inches(0.045),
            domain_layout.branch_y - Inches(0.045),
            Inches(0.09),
            Inches(0.09),
        )
        _set_fill(branch, theme.branch_fill)
        _set_line(branch, theme.branch_outline, Pt(1.5))

    for track, track_y in zip(domain_layout.domain.tracks, domain_layout.track_ys):
        _add_connector(
            slide, domain_layout.branch_x, domain_layout.branch_y, layout.columns.start_x, track_y,
            theme.track_line_color, line_width,
        )
        line_end_x = layout.track_line_ends[f"{domain_layout.domain.id}.{track.id}"]
        _add_connector(
            slide, layout.columns.start_x, track_y, line_end_x, track_y,
            theme.track_line_color, line_width,
        )


def _render_event(slide, position: EventPosition, theme: Theme) -> None:
    if position.event.type == "milestone":
        marker = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            position.x - _MARKER_SIZE // 2,
            position.y - _MARKER_SIZE // 2,
            _MARKER_SIZE,
            _MARKER_SIZE,
        )
        _set_fill(marker, theme.milestone_fill)
        _set_line(marker, theme.milestone_outline, Pt(1.5))
    elif position.event.type == "delivery":
        marker = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            position.x - _MARKER_SIZE // 2,
            position.y - _MARKER_SIZE // 2,
            _MARKER_SIZE,
            _MARKER_SIZE,
        )
        _set_fill(marker, theme.delivery_fill)
        _set_line(marker, None)
    # type == "start" has no marker shape, label only.

    # Stack outward from the marker: [gap][highlight bar][label text], so the bar always
    # sits between the track line and the label, reading as an underline for "above"
    # labels and as a flag directly under the line for "below" labels.
    label_x = position.x - _LABEL_WIDTH // 2
    label_height = _LABEL_HEIGHT
    half_marker = _MARKER_SIZE // 2
    bar_height = _HIGHLIGHT_HEIGHT if position.event.highlight else Emu(0)

    if position.label_position == "above":
        bar_y = position.y - half_marker - _LABEL_GAP - bar_height
        label_y = bar_y - label_height
        anchor = MSO_ANCHOR.BOTTOM
    else:
        bar_y = position.y + half_marker + _LABEL_GAP
        label_y = bar_y + bar_height
        anchor = MSO_ANCHOR.TOP

    if position.event.highlight:
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, label_x, bar_y, _LABEL_WIDTH, _HIGHLIGHT_HEIGHT)
        _set_fill(bar, theme.highlight_underline_color)
        _set_line(bar, None)

    _add_textbox(
        slide,
        label_x,
        label_y,
        _LABEL_WIDTH,
        label_height,
        position.event.label,
        theme.font,
        theme.font.label_size,
        theme.label_text_color,
        align=PP_ALIGN.CENTER,
        anchor=anchor,
    )


_MERGE_GUTTER_WIDTH = Inches(0.35)


def _render_merge(slide, start_x: int, start_y: int, end_x: int, end_y: int, color: str, width: Emu) -> None:
    """Draw a track-termination merge without sweeping a long diagonal across
    every row between source and target.

    The source's row is already empty past `start_x` (its line was shortened
    there), so a flat tail at `start_y` crosses nothing no matter how long it
    runs. Only the short curved drop at the end actually spans other rows'
    y-positions, and confining it to a narrow x-band keeps that crossing to a
    thin sliver instead of a wide diagonal band.
    """
    gutter_x = end_x - _MERGE_GUTTER_WIDTH
    if gutter_x > start_x:
        _add_connector(slide, start_x, start_y, gutter_x, start_y, color, width)
        _add_connector(slide, gutter_x, start_y, end_x, end_y, color, width, curved=True)
    else:
        _add_connector(slide, start_x, start_y, end_x, end_y, color, width, curved=True)


def _render_dependency(slide, dependency_layout: DependencyLayout, theme: Theme) -> None:
    dep = dependency_layout.dependency

    if dependency_layout.terminates_source:
        # This track's line already stops at `start` (see track_line_ends); draw a
        # curved solid continuation into the target so the two visually become one
        # line, rather than an annotation arrow pointing at an otherwise-unrelated
        # point. A curve reads as a merge; a straight diagonal reads as a pointer.
        _render_merge(
            slide,
            dependency_layout.start.x,
            dependency_layout.start.y,
            dependency_layout.end.x,
            dependency_layout.end.y,
            theme.track_line_color,
            Pt(1.5),
        )
        return

    connector = _add_connector(
        slide,
        dependency_layout.start.x,
        dependency_layout.start.y,
        dependency_layout.end.x,
        dependency_layout.end.y,
        theme.track_line_color,
        Pt(1.25),
        dashed=(dep.style == "dashed"),
    )
    _add_arrowhead(connector, end="tail", arrow_type="triangle")

    if dep.label:
        mid_x = (dependency_layout.start.x + dependency_layout.end.x) // 2
        mid_y = (dependency_layout.start.y + dependency_layout.end.y) // 2
        label_width = Inches(0.9)
        label_height = Inches(0.18)
        label_x = mid_x - label_width // 2
        label_y = mid_y - label_height // 2
        # Opaque backing so the label stays legible where it crosses track lines/markers.
        backing = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, label_x, label_y, label_width, label_height)
        _set_fill(backing, theme.background_fill)
        _set_line(backing, None)
        _add_textbox(
            slide,
            label_x,
            label_y,
            label_width,
            label_height,
            dep.label,
            theme.font,
            theme.font.label_size - 1,
            theme.label_text_color,
        )


def _render_footer(slide, layout: RoadmapLayout, theme: Theme) -> None:
    geom = layout.geometry
    footer_y = geom.slide_height - geom.footer_height
    _add_textbox(
        slide,
        geom.left_margin,
        footer_y,
        Inches(3.0),
        geom.footer_height,
        layout.roadmap.footer_link_text,
        theme.font,
        theme.font.footer_size,
        theme.footer_text_color,
        align=PP_ALIGN.LEFT,
        anchor=MSO_ANCHOR.MIDDLE,
    )
    _add_textbox(
        slide,
        geom.slide_width - geom.right_margin - Inches(2.0),
        footer_y,
        Inches(2.0),
        geom.footer_height,
        layout.roadmap.confidentiality_text,
        theme.font,
        theme.font.footer_size,
        theme.footer_text_color,
        align=PP_ALIGN.RIGHT,
        anchor=MSO_ANCHOR.MIDDLE,
    )


def render_roadmap(
    layout: RoadmapLayout,
    output_path: str | Path,
    theme: Theme,
    yaml_path: str | Path,
    cli_icons_dir: str | None = None,
) -> None:
    geom = layout.geometry
    icons_dir = resolve_icon_dir(yaml_path, layout.roadmap.icon_dir, cli_icons_dir)

    presentation = Presentation()
    presentation.slide_width = geom.slide_width
    presentation.slide_height = geom.slide_height
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])

    background = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, geom.slide_width, geom.slide_height)
    _set_fill(background, theme.background_fill)
    _set_line(background, None)
    background.shadow.inherit = False

    _render_title(slide, layout, theme)
    _render_header(slide, layout, theme)

    for domain_layout in layout.domain_layouts:
        _render_domain_badge(slide, domain_layout, theme, icons_dir)
        _render_domain_tracks(slide, layout, domain_layout, theme)

    for position in layout.event_positions:
        _render_event(slide, position, theme)

    for dependency_layout in layout.dependency_layouts:
        _render_dependency(slide, dependency_layout, theme)

    _render_footer(slide, layout, theme)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    presentation.save(str(output_path))
