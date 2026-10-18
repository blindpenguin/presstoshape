from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QToolBar

from veccy.models.app_state import AppState
from veccy.views.actions import AppActions


class MainToolbar(QToolBar):
    def __init__(self, actions: AppActions) -> None:
        super().__init__("Main")
        self.setMovable(False)
        self.setIconSize(QSize(22, 22))
        self.addActions([actions.new, actions.open, actions.save])
        self.addSeparator()
        self.addActions([actions.undo, actions.redo])
        self.addSeparator()
        self.addAction(actions.zoom_out)
        self._zoom = QLabel()
        self._zoom.setMinimumWidth(48)
        self.addWidget(self._zoom)
        self.addActions([actions.zoom_in, actions.zoom_fit])

    def refresh(self, state: AppState) -> None:
        self._zoom.setText(f" {state.zoom_percent}% ")
