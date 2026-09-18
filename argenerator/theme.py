"""Colour/font theme, defaulting to the reference roadmap palette. Swappable like icons:
a user-supplied YAML/JSON file is merged over the defaults so partial overrides work."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel
from pptx.dml.color import RGBColor


class FontTheme(BaseModel):
    name: str = "Calibri"
    title_size: int = 28
    header_size: int = 10
    domain_badge_size: int = 10
    label_size: int = 8
    footer_size: int = 9


class Theme(BaseModel):
    background_fill: str = "#FFFFFF"
    title_color: str = "#4B2E83"

    domain_badge_fill: str = "#4B2E83"
    domain_badge_text: str = "#FFFFFF"

    header_fy_fill: str = "#BFBFBF"
    header_q_fill: str = "#D9D9D9"
    header_text: str = "#000000"

    track_line_color: str = "#4B2E83"

    milestone_outline: str = "#4B2E83"
    milestone_fill: str = "#FFFFFF"
    delivery_fill: str = "#4B2E83"
    branch_outline: str = "#4B2E83"
    branch_fill: str = "#FFFFFF"

    highlight_underline_color: str = "#E8622C"
    label_text_color: str = "#262626"

    footer_text_color: str = "#7F7F7F"

    font: FontTheme = FontTheme()


def load_theme(path: str | Path | None) -> Theme:
    if path is None:
        return Theme()
    raw = yaml.safe_load(Path(path).read_text()) or {}
    base = Theme().model_dump()
    merged = {**base, **raw}
    if isinstance(raw.get("font"), dict):
        merged["font"] = {**base["font"], **raw["font"]}
    return Theme.model_validate(merged)


def hex_to_rgbcolor(hex_str: str) -> RGBColor:
    return RGBColor.from_string(hex_str.lstrip("#").upper())
