"""Semantic icon aliases over Tabler SVGs in presstoshape/assets/icons/.

Regenerate with `uv run --group dev python scripts/generate_icons.py` after changing the mapping in that
script. Load through `presstoshape.views.icon_engine.icon(...)`, which renders them as true vectors at any size/DPI.
"""

from pathlib import Path

_DIR = Path(__file__).resolve().parent / "assets" / "icons"

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
TOOL_RECTANGLE = _DIR / "tool_rectangle.svg"
TOOL_ELLIPSE = _DIR / "tool_ellipse.svg"
TOOL_TEXT = _DIR / "tool_text.svg"
TOOL_NODE = _DIR / "tool_node.svg"

UNION = _DIR / "union.svg"
DIFFERENCE = _DIR / "difference.svg"
DELETE = _DIR / "delete.svg"

LAYER_ADD = _DIR / "layer_add.svg"
LAYER_DELETE = _DIR / "layer_delete.svg"

CURSOR_ROTATE = _DIR / "cursor_rotate.svg"
CURSOR_NODE_INSERT = _DIR / "cursor_node_insert.svg"
