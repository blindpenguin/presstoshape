from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QToolBar

from veccy.views.actions import AppActions
from veccy.views.keymap import TOOL_STRIP


class ToolPalette(QToolBar):
    """Vertical tool strip. Checked state comes from AppActions.refresh, so it needs no refresh of its own."""

    def __init__(self, actions: AppActions) -> None:
        super().__init__("Tools")
        self.setMovable(False)
        self.setOrientation(Qt.Orientation.Vertical)
        self.setIconSize(QSize(24, 24))
        for command_id in TOOL_STRIP:
            if command_id is None:
                self.addSeparator()
            else:
                self.addAction(actions[command_id])
