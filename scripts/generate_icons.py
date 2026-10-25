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
    "tool_pencil": "pencil",
    "tool_rectangle": "square",
    "tool_ellipse": "circle",
    "tool_text": "typography",
    "tool_node": "vector",
    "union": "layers-union",
    "difference": "layers-subtract",
    "intersection": "layers-intersect-2",
    "exclude": "layers-difference",
    "divide": "layers-intersect",
    "node_corner": "vector-triangle",
    "node_smooth": "ease-in-out",
    "node_symmetric": "ease-in-out-control-points",
    "make_line": "line",
    "make_curve": "vector-spline",
    "break_nodes": "scissors",
    "join_nodes": "arrows-join",
    "join_segment": "link",
    "delete_segment": "unlink",
    "path_close": "shape",
    "path_open": "route",
    "path_reverse": "arrows-exchange",
    "path_combine": "circles-relation",
    "path_split": "arrows-split-2",
    "delete": "trash",
    "layer_add": "square-plus",
    "layer_delete": "trash",
    "cursor_rotate": "rotate-clockwise",
    "cursor_node_insert": "pencil-plus",
    "cursor_pen_add": "crosshair",
    "cursor_pen_close": "circle-dot",
    "cursor_pen_continue": "arrow-guide",
    "cursor_corner": "border-corner-rounded",
    "settings": "settings",
    "settings_language": "language",
    "settings_canvas": "artboard",
    "orientation_portrait": "rectangle-vertical",
    "orientation_landscape": "rectangle",
    "align_start": "align-left",
    "align_middle": "align-center",
    "align_end": "align-right",
    "object_align_left": "layout-align-left",
    "object_align_hcenter": "layout-align-center",
    "object_align_right": "layout-align-right",
    "object_align_top": "layout-align-top",
    "object_align_vcenter": "layout-align-middle",
    "object_align_bottom": "layout-align-bottom",
    "distribute_x": "spacing-horizontal",
    "distribute_y": "spacing-vertical",
    "distribute_centers_x": "layout-distribute-vertical",
    "distribute_centers_y": "layout-distribute-horizontal",
    "snapping": "magnet",
    "visible": "eye",
    "hidden": "eye-off",
    "locked": "lock",
    "unlocked": "lock-open",
    "object_rect": "square",
    "object_ellipse": "circle",
    "object_path": "vector-bezier",
    "object_text": "typography",
    "object_group": "box-multiple",
    "object_composite": "layers-union",
    "object_clip": "crop",
    "object_mask": "mask",
    "object_image": "photo",
    "image_place": "photo-plus",
    "image_replace": "replace",
    "image_references_hidden": "photo-off",
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
