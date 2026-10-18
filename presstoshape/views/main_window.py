from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from presstoshape.editing.operations import documents
from presstoshape.editing.session import Session
from presstoshape.version import app_version
from presstoshape.views import menu_bar_view, window_placement
from presstoshape.views.actions import AppActions
from presstoshape.views.canvas_view import CanvasView
from presstoshape.views.edit_bar_view import EditBar
from presstoshape.views.export_dialog import ExportPngDialog
from presstoshape.views.layers_view import LayersPanel
from presstoshape.views.left_sidebar_view import ToolPalette
from presstoshape.views.status_bar_view import StatusBar
from presstoshape.views.tool_options_view import TITLES, ToolOptionsPanel
from presstoshape.views.toolbar_view import MainToolbar

_SVG_FILTER = "SVG files (*.svg);;All files (*)"
_PNG_FILTER = "PNG image (*.png)"
_DOCK_WIDTH = 240
_TOOL_DOCK_WIDTH = 200


class MainWindow(QMainWindow):
    """Top view: assembles the panels and re-renders all of them from state after every session change."""

    def __init__(self, session: Session, settings: QSettings | None = None) -> None:
        """`settings` stores the window placement; None (screenshots, self-test) leaves the user's untouched."""
        super().__init__()
        self._settings = settings
        self._state = session.state
        self._session = session
        self._force_close = False

        self.canvas = CanvasView(session)
        self._edit_bar = EditBar(session)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._edit_bar)
        central_layout.addWidget(self.canvas)
        self.setCentralWidget(central)

        self._actions = AppActions(self, session, self._window_commands())
        menu_bar_view.build(self.menuBar(), self._actions)
        self._toolbar = MainToolbar(self._actions)
        self.addToolBar(self._toolbar)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, ToolPalette(self._actions))

        self._tool_options = ToolOptionsPanel(session)
        # Left dock area sits inside the left toolbar area, so this lands between tool strip and canvas.
        self._tool_dock = self._add_dock("Tool", self._tool_options, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._tool_dock.setFixedWidth(_TOOL_DOCK_WIDTH)
        self._layers = LayersPanel(session)
        self._add_dock("Layers", self._layers)

        self._status = StatusBar()
        self.setStatusBar(self._status)
        self.canvas.hint_changed.connect(self._status.show_hint)

        session.subscribe(self.refresh)
        self.refresh()

    def _add_dock(
        self, title: str, widget: QWidget, area: Qt.DockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea
    ) -> QDockWidget:
        dock = QDockWidget(title)
        dock.setWidget(widget)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setMinimumWidth(_DOCK_WIDTH)
        self.addDockWidget(area, dock)
        return dock

    def refresh(self) -> None:
        state = self._state
        self.setWindowTitle(f"{self._document_name()}[*] — PressToShape")
        self.setWindowModified(state.dirty)
        self._tool_dock.setWindowTitle(TITLES[state.active_tool])
        views = (
            self._actions,
            self._toolbar,
            self._edit_bar,
            self.canvas,
            self._tool_options,
            self._layers,
            self._status,
        )
        for view in views:
            view.refresh(state)

    def _window_commands(self) -> dict[str, Callable[[], object]]:
        return {
            "file.new": self.new_document,
            "file.open": self.open_document,
            "file.save": self.save_document,
            "file.save_as": self.save_document_as,
            "file.export_png": self.export_png,
            "file.quit": self.close,
            "view.zoom_fit": self.fit_to_window,
            "help.about": self.show_about,
        }

    def _document_name(self) -> str:
        return Path(self._state.file_path).name if self._state.file_path else "Untitled"

    # --- window commands (dialogs, viewport) ---------------------------------

    def new_document(self) -> None:
        if self._confirm_discard():
            documents.new_document(self._session)
            self.canvas.center_artboard()

    def open_document(self) -> None:
        if not self._confirm_discard():
            return
        start = str(Path(self._state.file_path).parent) if self._state.file_path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open SVG", start, _SVG_FILTER)
        if path and documents.open_file(self._session, path):
            self.canvas.fit_artboard()

    def save_document(self) -> bool:
        if self._state.file_path is None:
            return self.save_document_as()
        return documents.save_file(self._session)

    def save_document_as(self) -> bool:
        path, _ = QFileDialog.getSaveFileName(self, "Save SVG", self._state.file_path or "untitled.svg", _SVG_FILTER)
        if not path:
            return False
        if not path.lower().endswith(".svg"):
            path += ".svg"
        return documents.save_file(self._session, path)

    def export_png(self) -> None:
        scale = ExportPngDialog.ask(self._state.document, self._state.export.scale, self)
        if scale is None:
            return
        stem = Path(self._state.file_path).with_suffix(".png") if self._state.file_path else Path("untitled.png")
        path, _ = QFileDialog.getSaveFileName(self, "Export PNG", str(stem), _PNG_FILTER)
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        documents.export_png(self._session, path, scale)

    def fit_to_window(self) -> None:
        self.canvas.fit_artboard()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About PressToShape",
            f"PressToShape {app_version()}\n\n"
            "An open-source vector drawing application for artists.\n\nLicensed under the GNU GPL v3.",
        )

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
        if self._settings is not None:
            window_placement.save(self, self._settings)
        self.canvas.shutdown()
        super().closeEvent(event)
