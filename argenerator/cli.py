"""Command-line entry point: `argenerator render roadmap.yaml -o roadmap.pptx`."""

from __future__ import annotations

from pathlib import Path

import click

from argenerator.layout import LayoutError, compute_layout
from argenerator.render_pptx import render_roadmap
from argenerator.schema import SchemaError, load_roadmap
from argenerator.theme import load_theme


@click.group()
def main() -> None:
    """argenerator: render architecture roadmaps (YAML) to PowerPoint slides."""


@main.command()
@click.argument("roadmap_path", type=click.Path(exists=True, dir_okay=False))
@click.option("-o", "--output", "output_path", required=True, type=click.Path(dir_okay=False), help="Output .pptx path")
@click.option("--icons", "icons_dir", type=click.Path(exists=True, file_okay=False), default=None, help="Directory of domain icon images (overrides roadmap.icon_dir)")
@click.option("--theme", "theme_path", type=click.Path(exists=True, dir_okay=False), default=None, help="Theme YAML/JSON file overriding the default palette")
def render(roadmap_path: str, output_path: str, icons_dir: str | None, theme_path: str | None) -> None:
    """Render ROADMAP_PATH (a roadmap YAML file) to a .pptx slide."""
    try:
        roadmap = load_roadmap(roadmap_path)
        resolved_theme_path = theme_path
        if resolved_theme_path is None and roadmap.theme:
            resolved_theme_path = str(Path(roadmap_path).resolve().parent / roadmap.theme)
        theme = load_theme(resolved_theme_path)
        layout = compute_layout(roadmap)
        render_roadmap(layout, output_path, theme, roadmap_path, cli_icons_dir=icons_dir)
    except (SchemaError, LayoutError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Wrote {output_path}")


@main.command()
@click.argument("roadmap_path", type=click.Path(exists=True, dir_okay=False))
def validate(roadmap_path: str) -> None:
    """Validate ROADMAP_PATH without rendering."""
    try:
        roadmap = load_roadmap(roadmap_path)
    except SchemaError as exc:
        raise click.ClickException(str(exc)) from exc
    n_events = sum(len(t.events) for d in roadmap.domains for t in d.tracks)
    click.echo(f"OK: {len(roadmap.domains)} domains, {n_events} events, {len(roadmap.dependencies)} dependencies")


if __name__ == "__main__":
    main()
