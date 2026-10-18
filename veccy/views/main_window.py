from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMainWindow, QMessageBox, QWidget

from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState
from veccy.views import menu_bar_view
from veccy.views.actions import AppActions
from veccy.views.canvas_view import CanvasView
from veccy.views.layers_view import LayersPanel
from veccy.views.left_sidebar_view import ToolPalette
from veccy.views.properties_view import PropertiesPanel
from veccy.views.status_bar_view import StatusBar
from veccy.views.toolbar_view import MainToolbar

_SVG_FILTER = "SVG files (*.svg);;All files (*)"
_DOCK_WIDTH = 240


class MainWindow(QMainWindow):
    """Top view: assembles the panels and re-renders all of them from state on every controller change."""

    def __init__(self, state: AppState, controller: AppController) -> None:
        super().__init__()
        self._state = state
        self._controller = controller
        self._force_close = False

        self.canvas = CanvasView(controller)
        self.setCentralWidget(self.canvas)

        self._actions = AppActions(self, self, controller)
        menu_bar_view.build(self.menuBar(), self._actions)
        self._toolbar = MainToolbar(self._actions)
        self.addToolBar(self._toolbar)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, ToolPalette(self._actions))

        self._properties = PropertiesPanel(controller)
        self._layers = LayersPanel(controller)
        self._add_dock("Properties", self._properties)
        self._add_dock("Layers", self._layers)

        self._status = StatusBar()
        self.setStatusBar(self._status)

        controller.subscribe(self.refresh)
        self.refresh()

    def _add_dock(self, title: str, widget: QWidget) -> None:
        dock = QDockWidget(title)
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setMinimumWidth(_DOCK_WIDTH)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def refresh(self) -> None:
        state = self._state
        self.setWindowTitle(f"{self._document_name()}[*] — veccy")
        self.setWindowModified(state.dirty)
        for view in (self._actions, self._toolbar, self.canvas, self._properties, self._layers, self._status):
            view.refresh(state)

    def _document_name(self) -> str:
        return Path(self._state.file_path).name if self._state.file_path else "Untitled"

    # --- window commands (dialogs, viewport) ---------------------------------

    def new_document(self) -> None:
        if self._confirm_discard():
            self._controller.new_document()
            self.canvas.center_artboard()

    def open_document(self) -> None:
        if not self._confirm_discard():
            return
        start = str(Path(self._state.file_path).parent) if self._state.file_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open SVG", start, _SVG_FILTER)
        if path and self._controller.open_file(path):
            self.canvas.fit_artboard()

    def save_document(self) -> bool:
        if self._state.file_path is None:
            return self.save_document_as()
        return self._controller.save_file()

    def save_document_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Save SVG", self._state.file_path or "untitled.svg", _SVG_FILTER)
        if not path:
            return False
        if not path.lower().endswith(".svg"):
            path += ".svg"
        return self._controller.save_file(path)

    def fit_to_window(self) -> None:
        self.canvas.fit_artboard()

    def show_about(self) -> None:
        QMessageBox.about(self, "About veccy", "veccy — a small SVG editor built on PySide6.")

    def _confirm_discard(self) -> bool:
        if not self._state.dirty:
            return True
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save changes to {self._document_name()}?",
            buttons.Save | buttons.Discard | buttons.Cancel,
            buttons.Save,
        )
        if answer == buttons.Save:
            return self.save_document()
        return answer == buttons.Discard

    def close_without_prompt(self) -> None:
        self._force_close = True
        self.close()

    def closeEvent(self, event):
        if not self._force_close and not self._confirm_discard():
            event.ignore()
            return
        self.canvas.shutdown()
        super().closeEvent(event)
