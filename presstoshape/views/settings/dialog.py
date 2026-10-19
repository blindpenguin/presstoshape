from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from presstoshape.i18n import _
from presstoshape.views.icon_engine import icon
from presstoshape.views.settings.canvas_page import CanvasPage
from presstoshape.views.settings.general_page import GeneralPage
from presstoshape.views.settings.language_page import LanguagePage
from presstoshape.views.settings.pages import SettingsContext, SettingsPage

# Category order in the list.
PAGES: list[type[SettingsPage]] = [GeneralPage, LanguagePage, CanvasPage]

_LIST_WIDTH = 170


class SettingsDialog(QDialog):
    """Changes apply right away (no OK/Apply); Close or Esc closes."""

    def __init__(self, context: SettingsContext, parent: QWidget | None = None, page: int = 0) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self._categories = QListWidget()
        self._categories.setFixedWidth(_LIST_WIDTH)
        self._categories.setIconSize(QSize(20, 20))
        self._pages = QStackedWidget()
        for page_type in PAGES:
            page_widget = page_type(context)
            self._pages.addWidget(page_widget)
            QListWidgetItem(icon(page_type.icon), _(page_type.title), self._categories)
        self._categories.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._categories.setCurrentRow(min(max(page, 0), len(PAGES) - 1))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        body = QHBoxLayout()
        body.addWidget(self._categories)
        body.addWidget(self._pages, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(body, 1)
        layout.addWidget(buttons)
        self.resize(680, 440)

    @property
    def page(self) -> int:
        return self._categories.currentRow()
