from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QDockWidget, QFileDialog, QMainWindow, QMessageBox, QVBoxLayout, QWidget

from presstoshape import i18n
from presstoshape.editing.operations import clipboard as clipboard_ops
from presstoshape.editing.operations import documents, view
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.version import app_version
from presstoshape.views import app_settings, clipboard, menu_bar_view, window_placement
from presstoshape.views.actions import AppActions
from presstoshape.views.canvas_view import CanvasView
from presstoshape.views.edit_bar_view import EditBar
from presstoshape.views.export_dialog import ExportPngDialog
from presstoshape.views.layers_view import LayersPanel
from presstoshape.views.left_sidebar_view import ToolPalette
from presstoshape.views.new_document_dialog import OPEN, NewDocumentDialog, StartChoices
from presstoshape.views.settings.dialog import SettingsDialog
from presstoshape.views.settings.pages import SettingsContext
from presstoshape.views.status_bar_view import StatusBar
from presstoshape.views.tool_options_view import TITLES, ToolOptionsPanel
from presstoshape.views.toolbar_view import MainToolbar

# File dialog filters, translated when a dialog opens.
_NATIVE_FILTER = N_("PressToShape (*.p2s)")
_SVG_FILTER = N_("SVG (*.svg)")
_PNG_FILTER = N_("PNG image (*.png)")
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
        # The Settings window reopens on the last category and size during a session.
        self._settings_page = 0
        self._settings_size: QSize | None = None

        self.canvas = CanvasView(session, app_settings.renderer(settings) if settings is not None else "auto")
        self._edit_bar = EditBar(session)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self._edit_bar)
        central_layout.addWidget(self.canvas)
        self.setCentralWidget(central)

        self._actions = AppActions(self, session, self._window_commands())
        self._recent_menu = menu_bar_view.build(self.menuBar(), self._actions)
        self._recent_menu.aboutToShow.connect(self._fill_recent_menu)
        self._toolbar = MainToolbar(self._actions)
        self.addToolBar(self._toolbar)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, ToolPalette(self._actions))

        self._tool_options = ToolOptionsPanel(session)
        # Left dock area sits inside the left toolbar area, so this lands between tool strip and canvas.
        self._tool_dock = self._add_dock(_("Tool"), self._tool_options, Qt.DockWidgetArea.LeftDockWidgetArea)
        self._tool_dock.setFixedWidth(_TOOL_DOCK_WIDTH)
        self._layers = LayersPanel(session)
        self._add_dock(_("Layers"), self._layers)

        self._status = StatusBar()
        self.setStatusBar(self._status)
        self.canvas.hint_changed.connect(self._status.show_hint)

        QGuiApplication.clipboard().dataChanged.connect(self._update_paste_actions)
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
        self._tool_dock.setWindowTitle(_(TITLES[state.active_tool]))
        views = (
            self._actions,
            self._toolbar,
            self._edit_bar,
            self.canvas,
            self._tool_options,
            self._layers,
            self._status,
        )
        for panel in views:
            panel.refresh(state)
        for command_id in ("edit.cut", "edit.copy"):
            self._actions.set_enabled(command_id, bool(state.selection))
        self._update_paste_actions()
        # Screenshots and the self-test run without user settings, so there is nothing to change.
        self._actions.set_enabled("edit.settings", self._settings is not None)

    def _update_paste_actions(self) -> None:
        offered = clipboard.can_paste()
        for command_id in ("edit.paste", "edit.paste_in_place"):
            self._actions.set_enabled(command_id, offered)

    def _window_commands(self) -> dict[str, Callable[[], object]]:
        return {
            "file.new": self.new_document,
            "file.open": self.open_document,
            "file.save": self.save_document,
            "file.save_as": self.save_document_as,
            "file.export_png": self.export_png,
            "file.quit": self.close,
            "edit.cut": self.cut,
            "edit.copy": self.copy,
            "edit.paste": self.paste,
            "edit.paste_in_place": self.paste_in_place,
            "edit.settings": self.open_settings,
            "view.zoom_fit": self.fit_to_window,
            "help.about": self.show_about,
        }

    def _document_name(self) -> str:
        return Path(self._state.file_path).name if self._state.file_path else _("Untitled")

    # --- window commands (dialogs, viewport) ---------------------------------

    def new_document(self) -> None:
        """File → New: the New Document dialog; unsaved changes are asked about after Create."""
        last = app_settings.last_new_document(self._settings) if self._settings is not None else None
        dialog = NewDocumentDialog(last, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and self._confirm_discard():
            self._create_document(dialog.preset_id, dialog.setup)

    def start(self) -> None:
        """Right after the window is shown: the New Document dialog, or the last used size without it."""
        if self._settings is None:
            return
        if app_settings.show_start_dialog(self._settings):
            self.show_start_dialog()
        elif (last := app_settings.last_new_document(self._settings)) is not None:
            self._create_document(*last)

    def show_start_dialog(self, error: str | None = None) -> None:
        settings = self._settings
        last = app_settings.last_new_document(settings)
        start = StartChoices(app_settings.recent_files(settings), app_settings.show_start_dialog(settings), error)
        dialog = NewDocumentDialog(last, start, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        app_settings.set_show_start_dialog(settings, bool(dialog.show_at_startup))
        if not accepted:
            # Cancel still gives the last used size, as if no dialog had been shown.
            if last is not None:
                self._create_document(*last)
            return
        if dialog.open_path is None:
            self._create_document(dialog.preset_id, dialog.setup)
            return
        path = dialog.open_path
        if path == OPEN:
            path, _chosen = QFileDialog.getOpenFileName(self, _("Open"), "", self._open_filters())
            if not path:
                self.show_start_dialog()
                return
        if not self.open_path(path):
            self.show_start_dialog(self._state.status_message)

    def _create_document(self, preset_id: str | None, setup: documents.DocumentSetup) -> None:
        documents.new_document(self._session, setup)
        self.canvas.fit_artboard()
        if self._settings is not None:
            app_settings.set_last_new_document(self._settings, preset_id, setup)

    def open_document(self) -> None:
        if not self._confirm_discard():
            return
        start = str(Path(self._state.file_path).parent) if self._state.file_path else ""
        path, _chosen = QFileDialog.getOpenFileName(self, _("Open"), start, self._open_filters())
        if path:
            self.open_path(path)

    @staticmethod
    def _open_filters() -> str:
        names = [_("PressToShape and SVG (*.p2s *.svg)"), _(_NATIVE_FILTER), _(_SVG_FILTER), _("All files (*)")]
        return ";;".join(names)

    def open_path(self, path: str) -> bool:
        """Opens `path` (dirty check already done) and shows it; a file that fails is dropped from recent files."""
        if not documents.open_file(self._session, path):
            if self._settings is not None:
                app_settings.remove_recent_file(self._settings, path)
            return False
        if self._settings is not None:
            app_settings.add_recent_file(self._settings, path)
        center = view.take_restore_view_center(self._session)
        if center is None:
            self.canvas.fit_artboard()
        else:
            self.canvas.center_on(center)
        return True

    def open_recent(self, path: str) -> None:
        if self._confirm_discard():
            self.open_path(path)

    def _fill_recent_menu(self) -> None:
        menu = self._recent_menu
        menu.clear()
        paths = app_settings.recent_files(self._settings) if self._settings is not None else []
        if not paths:
            menu.addAction(_("No recent files")).setEnabled(False)
            return
        for number, path in enumerate(paths, 1):
            action = menu.addAction(f"&{number} {Path(path).name.replace('&', '&&')}")
            action.setToolTip(path)
            action.triggered.connect(lambda _checked=False, chosen=path: self.open_recent(chosen))
        menu.addSeparator()
        clear = menu.addAction(_("Clear Recent Files"))
        clear.triggered.connect(lambda: app_settings.clear_recent_files(self._settings))

    def _remember_saved(self, saved: bool) -> bool:
        if saved and self._settings is not None and self._state.file_path is not None:
            app_settings.add_recent_file(self._settings, self._state.file_path)
        return saved

    def save_document(self) -> bool:
        if self._state.file_path is None:
            return self.save_document_as()
        return self._remember_saved(documents.save_file(self._session, view_center=self.canvas.view_center()))

    def save_document_as(self) -> bool:
        current = self._state.file_path
        keeps_svg = current is not None and not documents.is_native(current)
        suggested = current or _("untitled") + documents.NATIVE_SUFFIX
        native_filter, svg_filter = _(_NATIVE_FILTER), _(_SVG_FILTER)
        chosen_filter = svg_filter if keeps_svg else native_filter
        filters = f"{native_filter};;{svg_filter}"
        path, chosen_filter = QFileDialog.getSaveFileName(self, _("Save As"), suggested, filters, chosen_filter)
        if not path:
            return False
        if Path(path).suffix.lower() not in (documents.NATIVE_SUFFIX, ".svg"):
            path += ".svg" if chosen_filter == svg_filter else documents.NATIVE_SUFFIX
        return self._remember_saved(documents.save_file(self._session, path, view_center=self.canvas.view_center()))

    def export_png(self) -> None:
        scale = ExportPngDialog.ask(self._state.document, self._state.export.scale, self)
        if scale is None:
            return
        current = self._state.file_path
        stem = Path(current).with_suffix(".png") if current else Path(_("untitled") + ".png")
        path, _chosen = QFileDialog.getSaveFileName(self, _("Export PNG"), str(stem), _(_PNG_FILTER))
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        documents.export_png(self._session, path, scale)

    def cut(self) -> None:
        content = clipboard_ops.cut_selection(self._session)
        if content is not None:
            clipboard.put(content)

    def copy(self) -> None:
        content = clipboard_ops.copy_selection(self._session)
        if content is not None:
            clipboard.put(content)

    def paste(self) -> None:
        clipboard_ops.paste(self._session, *clipboard.read(), self.canvas.view_center())

    def paste_in_place(self) -> None:
        clipboard_ops.paste(self._session, *clipboard.read(), None)

    def open_settings(self) -> None:
        if self._settings is None:
            return
        context = SettingsContext(self._settings, i18n.active_language(), app_settings.translations_folder())
        dialog = SettingsDialog(context, self, self._settings_page)
        if self._settings_size is not None:
            dialog.resize(self._settings_size)
        dialog.exec()
        self._settings_page, self._settings_size = dialog.page, dialog.size()

    def fit_to_window(self) -> None:
        self.canvas.fit_artboard()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            _("About PressToShape"),
            _(
                "PressToShape {version}\n\n"
                "An open-source vector drawing application for artists.\n\nLicensed under the GNU GPL v3."
            ).format(version=app_version()),
        )

    def _confirm_discard(self) -> bool:
        if not self._state.dirty:
            return True
        buttons = QMessageBox.StandardButton
        answer = QMessageBox.question(
            self,
            _("Unsaved changes"),
            _("Save changes to {name}?").format(name=self._document_name()),
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
        QGuiApplication.clipboard().dataChanged.disconnect(self._update_paste_actions)
        if self._settings is not None:
            window_placement.save(self, self._settings)
        self.canvas.shutdown()
        super().closeEvent(event)
