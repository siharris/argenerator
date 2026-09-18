"""Domain icon resolution. Icons are swappable image files, never hardcoded/embedded,
resolved with the following precedence (highest first):

1. explicit `--icons` CLI flag
2. `Roadmap.icon_dir` field in the YAML
3. an `icons/` folder next to the roadmap YAML file
4. the bundled default icon shipped with argenerator
"""

from __future__ import annotations

from pathlib import Path

_DEFAULT_ICON = Path(__file__).parent / "assets" / "icons" / "default_gear.png"


class IconError(FileNotFoundError):
    pass


def resolve_icon_dir(
    yaml_path: str | Path,
    roadmap_icon_dir: str | None,
    cli_icons_dir: str | None,
) -> Path | None:
    """Return the directory to look up icon filenames in, or None if only the
    bundled default is available."""
    yaml_dir = Path(yaml_path).resolve().parent

    if cli_icons_dir is not None:
        return Path(cli_icons_dir)
    if roadmap_icon_dir is not None:
        candidate = Path(roadmap_icon_dir)
        return candidate if candidate.is_absolute() else yaml_dir / candidate
    local = yaml_dir / "icons"
    if local.is_dir():
        return local
    return None


def resolve_icon(
    icon_name: str | None,
    icon_dir: Path | None,
) -> Path:
    """Resolve a domain's `icon` filename to an actual file path, falling back to
    the bundled default gear icon if unset or not found."""
    if icon_name and icon_dir is not None:
        candidate = icon_dir / icon_name
        if candidate.is_file():
            return candidate
    return _DEFAULT_ICON
