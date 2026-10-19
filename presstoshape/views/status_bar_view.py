from PySide6.QtWidgets import QLabel, QStatusBar

from presstoshape.editing.operations.view import tool_name
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState


class StatusBar(QStatusBar):
    def __init__(self) -> None:
        super().__init__()
        self._message = QLabel()
        self._info = QLabel()
        self.addWidget(self._message, 1)
        self.addPermanentWidget(self._info)
        self._status_message = ""
        self._hint: str | None = None

    def refresh(self, state: AppState) -> None:
        self._status_message = state.status_message
        self._message.setText(self._hint or self._status_message)
        info = _("Tool: {tool}  |  {count} selected  |  {zoom}%")
        tool = tool_name(state.active_tool)
        self._info.setText(info.format(tool=tool, count=len(state.selection), zoom=state.zoom_percent))

    def show_hint(self, hint: str | None) -> None:
        """Transient gesture text shown over the status message until cleared."""
        self._hint = hint
        self._message.setText(hint or self._status_message)
