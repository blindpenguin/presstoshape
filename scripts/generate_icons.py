"""Copies the app's icon set from Tabler Icons (pytablericons' bundled outline SVGs) into presstoshape/assets/icons/.

Run with `uv run --group dev python scripts/generate_icons.py` whenever the mapping below changes. Output is
committed — the running app only loads the static SVGs, it never imports pytablericons. Files keep Tabler's
`stroke="currentColor"`; presstoshape.views.icon_engine substitutes the theme color at render time.
"""

import re
from pathlib import Path

import pytablericons

ICONS = {
    "new": "file",
    "open": "folder-open",
    "save": "device-floppy",
    "undo": "arrow-back-up",
    "redo": "arrow-forward-up",
    "zoom_in": "zoom-in",
    "zoom_out": "zoom-out",
    "zoom_fit": "zoom-scan",
    "tool_select": "pointer",
    "tool_pen": "vector-bezier-2",
    "tool_rectangle": "square",
    "tool_ellipse": "circle",
    "tool_text": "typography",
    "tool_node": "vector",
    "union": "layers-union",
    "difference": "layers-subtract",
    "intersection": "layers-intersect-2",
    "exclude": "layers-difference",
    "divide": "layers-intersect",
    "delete": "trash",
    "layer_add": "square-plus",
    "layer_delete": "trash",
    "cursor_rotate": "rotate-clockwise",
    "cursor_node_insert": "pencil-plus",
}


def main() -> None:
    src_dir = Path(pytablericons.__file__).resolve().parent / "icons" / "outline"
    out_dir = Path(__file__).resolve().parent.parent / "presstoshape" / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    for stale in out_dir.iterdir():
        if stale.stem not in ICONS or stale.suffix != ".svg":
            stale.unlink()
            print(f"removed {stale.name}")

    for name, tabler_name in ICONS.items():
        svg = (src_dir / f"{tabler_name}.svg").read_text()
        # Drop Tabler's metadata comment header so the file starts at <svg>.
        svg = re.sub(r"\A\s*<!--.*?-->\s*", "", svg, flags=re.S)
        (out_dir / f"{name}.svg").write_text(svg)
        print(f"wrote {name}.svg")


if __name__ == "__main__":
    main()
