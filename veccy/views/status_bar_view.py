from PySide6.QtWidgets import QLabel, QStatusBar

from veccy.models.app_state import AppState


class StatusBar(QStatusBar):
    def __init__(self) -> None:
        super().__init__()
        self._message = QLabel()
        self._info = QLabel()
        self.addWidget(self._message, 1)
        self.addPermanentWidget(self._info)

    def refresh(self, state: AppState) -> None:
        self._message.setText(state.status_message)
        self._info.setText(
            f"Tool: {state.active_tool.name.title()}  |  {len(state.selection)} selected  |  {state.zoom_percent}%"
        )
