from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QWidget

from veccy import icons
from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState, Tool
from veccy.views.icon_engine import icon

Shortcut = str | QKeySequence.StandardKey | list[QKeySequence]

TOOLS = (
    (Tool.SELECT, icons.TOOL_SELECT, "&Select", "V"),
    (Tool.NODE, icons.TOOL_NODE, "&Node", "N"),
    (Tool.PEN, icons.TOOL_PEN, "&Pen", "P"),
    (Tool.RECTANGLE, icons.TOOL_RECTANGLE, "&Rectangle", "R"),
    (Tool.ELLIPSE, icons.TOOL_ELLIPSE, "&Ellipse", "E"),
    (Tool.TEXT, icons.TOOL_TEXT, "&Text", "T"),
)


class WindowCommands(Protocol):
    """Commands that need dialogs or the viewport, so they live on the window rather than the controller."""

    def new_document(self) -> None: ...
    def open_document(self) -> None: ...
    def save_document(self) -> bool: ...
    def save_document_as(self) -> bool: ...
    def export_png(self) -> None: ...
    def fit_to_window(self) -> None: ...
    def show_about(self) -> None: ...
    def close(self) -> bool: ...


class AppActions:
    """Every QAction in the app, shared by menu bar and toolbars so enabled/checked state stays in one place."""

    def __init__(self, parent: QWidget, window: WindowCommands, controller: AppController) -> None:
        self._parent = parent
        self._controller = controller
        c = controller

        self.new = self._make("&New", window.new_document, icons.NEW, QKeySequence.StandardKey.New)
        self.open = self._make("&Open…", window.open_document, icons.OPEN, QKeySequence.StandardKey.Open)
        self.save = self._make("&Save", window.save_document, icons.SAVE, QKeySequence.StandardKey.Save)
        self.save_as = self._make("Save &As…", window.save_document_as, shortcut=QKeySequence.StandardKey.SaveAs)
        self.export_png = self._make("&Export PNG…", window.export_png, shortcut="Ctrl+Shift+E")
        self.quit = self._make("&Quit", window.close, shortcut=QKeySequence.StandardKey.Quit)

        self.undo = self._make("&Undo", c.undo, icons.UNDO, QKeySequence.StandardKey.Undo)
        redo_keys = [*QKeySequence.keyBindings(QKeySequence.StandardKey.Redo), QKeySequence("Ctrl+Y")]
        self.redo = self._make("&Redo", c.redo, icons.REDO, redo_keys)
        self.select_all = self._make("Select &All", c.select_all, shortcut=QKeySequence.StandardKey.SelectAll)
        self.delete = self._make("&Delete", c.delete_selection, icons.DELETE, QKeySequence.StandardKey.Delete)
        self.union = self._make("&Union", lambda: c.combine("union"), icons.UNION, "Ctrl++")
        self.difference = self._make("D&ifference", lambda: c.combine("difference"), icons.DIFFERENCE, "Ctrl+-")
        self.object_to_path = self._make("&Object to Path", c.object_to_path, shortcut="Ctrl+Shift+C")

        self.zoom_in = self._make("Zoom &In", c.zoom_in, icons.ZOOM_IN, [QKeySequence("+"), QKeySequence("=")])
        self.zoom_out = self._make("Zoom &Out", c.zoom_out, icons.ZOOM_OUT, "-")
        self.zoom_fit = self._make("Zoom to &Fit", window.fit_to_window, icons.ZOOM_FIT, "5")
        self.zoom_actual = self._make("&Actual Size", lambda: c.set_zoom(100), shortcut="1")

        self.about = self._make("&About veccy", window.show_about)

        self.tool_group = QActionGroup(parent)
        self.tools: dict[Tool, QAction] = {}
        for tool, path, text, key in TOOLS:
            action = self._make(text, lambda t=tool: c.select_tool(t), path, key)
            action.setCheckable(True)
            self.tool_group.addAction(action)
            self.tools[tool] = action

    def _make(
        self, text: str, slot: Callable[[], object], path: Path | None = None, shortcut: Shortcut | None = None
    ) -> QAction:
        action = QAction(text, self._parent)
        if path is not None:
            action.setIcon(icon(path))
        if isinstance(shortcut, list):
            action.setShortcuts(shortcut)
        elif shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        if shortcut is not None:
            action.setToolTip(f"{text.replace('&', '')} ({action.shortcut().toString()})")
        # Lambda swallows triggered(checked) so it isn't passed into slots with optional args.
        action.triggered.connect(lambda: slot())
        return action

    def refresh(self, state: AppState) -> None:
        c = self._controller
        self.undo.setEnabled(c.can_undo)
        self.redo.setEnabled(c.can_redo)
        self.delete.setEnabled(bool(state.selection))
        self.union.setEnabled(c.can_combine())
        self.difference.setEnabled(c.can_combine())
        self.object_to_path.setEnabled(c.can_object_to_path())
        self.tools[state.active_tool].setChecked(True)
