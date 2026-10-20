"""Semantic icon aliases over Tabler SVGs in presstoshape/assets/icons/.

Regenerate with `uv run --group dev python scripts/generate_icons.py` after changing the mapping in that
script. Load through `presstoshape.views.icon_engine.icon(...)`, which renders them as true vectors at any size/DPI.
"""

from pathlib import Path

_DIR = Path(__file__).resolve().parent / "assets" / "icons"

# Full-color app mark (window, exe, installer); not recolored like the UI icons.
APP = Path(__file__).resolve().parent / "assets" / "app" / "presstoshape.svg"

NEW = _DIR / "new.svg"
OPEN = _DIR / "open.svg"
SAVE = _DIR / "save.svg"
UNDO = _DIR / "undo.svg"
REDO = _DIR / "redo.svg"
ZOOM_IN = _DIR / "zoom_in.svg"
ZOOM_OUT = _DIR / "zoom_out.svg"
ZOOM_FIT = _DIR / "zoom_fit.svg"

TOOL_SELECT = _DIR / "tool_select.svg"
TOOL_PEN = _DIR / "tool_pen.svg"
TOOL_PENCIL = _DIR / "tool_pencil.svg"
TOOL_RECTANGLE = _DIR / "tool_rectangle.svg"
TOOL_ELLIPSE = _DIR / "tool_ellipse.svg"
TOOL_TEXT = _DIR / "tool_text.svg"
TOOL_NODE = _DIR / "tool_node.svg"

UNION = _DIR / "union.svg"
DIFFERENCE = _DIR / "difference.svg"
INTERSECTION = _DIR / "intersection.svg"
EXCLUDE = _DIR / "exclude.svg"
DIVIDE = _DIR / "divide.svg"
DELETE = _DIR / "delete.svg"

LAYER_ADD = _DIR / "layer_add.svg"
LAYER_DELETE = _DIR / "layer_delete.svg"

SETTINGS = _DIR / "settings.svg"
SETTINGS_LANGUAGE = _DIR / "settings_language.svg"
SETTINGS_CANVAS = _DIR / "settings_canvas.svg"
ORIENTATION_PORTRAIT = _DIR / "orientation_portrait.svg"
ORIENTATION_LANDSCAPE = _DIR / "orientation_landscape.svg"

ALIGN_START = _DIR / "align_start.svg"
ALIGN_MIDDLE = _DIR / "align_middle.svg"
ALIGN_END = _DIR / "align_end.svg"

OBJECT_ALIGN_LEFT = _DIR / "object_align_left.svg"
OBJECT_ALIGN_HCENTER = _DIR / "object_align_hcenter.svg"
OBJECT_ALIGN_RIGHT = _DIR / "object_align_right.svg"
OBJECT_ALIGN_TOP = _DIR / "object_align_top.svg"
OBJECT_ALIGN_VCENTER = _DIR / "object_align_vcenter.svg"
OBJECT_ALIGN_BOTTOM = _DIR / "object_align_bottom.svg"
DISTRIBUTE_X = _DIR / "distribute_x.svg"
DISTRIBUTE_Y = _DIR / "distribute_y.svg"
DISTRIBUTE_CENTERS_X = _DIR / "distribute_centers_x.svg"
DISTRIBUTE_CENTERS_Y = _DIR / "distribute_centers_y.svg"
SNAPPING = _DIR / "snapping.svg"

CURSOR_ROTATE = _DIR / "cursor_rotate.svg"
CURSOR_NODE_INSERT = _DIR / "cursor_node_insert.svg"
