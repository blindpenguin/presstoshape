from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QToolBar

from veccy.models.app_state import AppState
from veccy.views.actions import AppActions
from veccy.views.keymap import MAIN_TOOLBAR, ZOOM_LABEL


class MainToolbar(QToolBar):
    def __init__(self, actions: AppActions) -> None:
        super().__init__("Main")
        self.setMovable(False)
        self.setIconSize(QSize(22, 22))
        self._zoom = QLabel()
        self._zoom.setMinimumWidth(48)
        for command_id in MAIN_TOOLBAR:
            if command_id is None:
                self.addSeparator()
            elif command_id == ZOOM_LABEL:
                self.addWidget(self._zoom)
            else:
                self.addAction(actions[command_id])

    def refresh(self, state: AppState) -> None:
        self._zoom.setText(f" {state.zoom_percent}% ")
