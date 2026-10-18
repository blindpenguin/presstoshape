from PySide6.QtWidgets import QLabel, QStatusBar

from veccy.models.app_state import AppState


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
        self._info.setText(
            f"Tool: {state.active_tool.name.title()}  |  {len(state.selection)} selected  |  {state.zoom_percent}%"
        )

    def show_hint(self, hint: str | None) -> None:
        """Transient gesture text shown over the status message until cleared."""
        self._hint = hint
        self._message.setText(hint or self._status_message)
