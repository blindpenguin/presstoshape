"""Shortcuts, icons and menu/toolbar layouts per command id. Presentation only; operations live in veccy.editing.

Ids come from three places: registered operations (`veccy.editing.registry`), tools (`veccy.tools.registry`) and
window commands (dialogs and viewport, `WINDOW_COMMANDS`, implemented by MainWindow).
"""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QKeySequence

from veccy import icons
from veccy.tools.registry import TOOLS

Keys = QKeySequence.StandardKey
# A tuple binds several shortcuts; standard keys expand to the platform's bindings when the action is built.
Shortcut = str | Keys | tuple[str | Keys, ...]


@dataclass(frozen=True)
class Binding:
    shortcut: Shortcut | None = None
    icon: Path | None = None


# Commands that need a dialog or the viewport; MainWindow maps each id to a method.
WINDOW_COMMANDS = {
    "file.new": "&New",
    "file.open": "&Open…",
    "file.save": "&Save",
    "file.save_as": "Save &As…",
    "file.export_png": "&Export PNG…",
    "file.quit": "&Quit",
    "view.zoom_fit": "Zoom to &Fit",
    "help.about": "&About veccy",
}

KEYMAP: dict[str, Binding] = {
    "file.new": Binding(Keys.New, icons.NEW),
    "file.open": Binding(Keys.Open, icons.OPEN),
    "file.save": Binding(Keys.Save, icons.SAVE),
    "file.save_as": Binding(Keys.SaveAs),
    "file.export_png": Binding("Ctrl+Shift+E"),
    "file.quit": Binding(Keys.Quit),
    "edit.undo": Binding(Keys.Undo, icons.UNDO),
    "edit.redo": Binding((Keys.Redo, "Ctrl+Y"), icons.REDO),
    "edit.select_all": Binding(Keys.SelectAll),
    "edit.delete": Binding(Keys.Delete, icons.DELETE),
    "path.union": Binding("Ctrl++", icons.UNION),
    "path.difference": Binding("Ctrl+-", icons.DIFFERENCE),
    "path.object_to_path": Binding("Ctrl+Shift+C"),
    "view.zoom_in": Binding(("+", "="), icons.ZOOM_IN),
    "view.zoom_out": Binding("-", icons.ZOOM_OUT),
    "view.zoom_fit": Binding("5", icons.ZOOM_FIT),
    "view.zoom_actual": Binding("1"),
    "tool.select": Binding("V", icons.TOOL_SELECT),
    "tool.node": Binding("N", icons.TOOL_NODE),
    "tool.pen": Binding("P", icons.TOOL_PEN),
    "tool.rectangle": Binding("R", icons.TOOL_RECTANGLE),
    "tool.ellipse": Binding("E", icons.TOOL_ELLIPSE),
    "tool.text": Binding("T", icons.TOOL_TEXT),
}

TOOL_IDS = [entry.id for entry in TOOLS]

# None is a separator.
MENUS: list[tuple[str, list[str | None]]] = [
    ("&File", ["file.new", "file.open", "file.save", "file.save_as", None, "file.export_png", None, "file.quit"]),
    ("&Edit", ["edit.undo", "edit.redo", None, "edit.select_all", "edit.delete"]),
    ("&Path", ["path.union", "path.difference", None, "path.object_to_path"]),
    ("&View", ["view.zoom_in", "view.zoom_out", "view.zoom_fit", "view.zoom_actual"]),
    ("&Tools", TOOL_IDS),
    ("&Help", ["help.about"]),
]

# The zoom percentage label sits between zoom out and zoom in; toolbar_view inserts it at this marker.
ZOOM_LABEL = "view.zoom_label"
MAIN_TOOLBAR: list[str | None] = [
    "file.new", "file.open", "file.save", None,
    "edit.undo", "edit.redo", None,
    "view.zoom_out", ZOOM_LABEL, "view.zoom_in", "view.zoom_fit",
]  # fmt: skip
TOOL_STRIP: list[str | None] = [*TOOL_IDS, None, "path.union", "path.difference", "edit.delete"]
