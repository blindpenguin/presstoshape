"""Align and distribute buttons in the right sidebar, below the layers."""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QComboBox, QGridLayout, QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from presstoshape.editing.operations import align
from presstoshape.editing.session import Session
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState
from presstoshape.views.actions import AppActions
from presstoshape.views.keymap import ALIGN_IDS, DISTRIBUTE_IDS

_ICON_SIZE = QSize(20, 20)


class AlignPanel(QWidget):
    """Buttons share the menu's actions, so they are enabled and labelled the same way."""

    def __init__(self, session: Session, actions: AppActions) -> None:
        super().__init__()
        self._session = session
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addLayout(self._buttons(ALIGN_IDS, actions, columns=3))
        layout.addLayout(self._buttons(DISTRIBUTE_IDS, actions, columns=4))
        reference_row = QHBoxLayout()
        reference_row.addWidget(QLabel(_("Relative to")))
        self._reference = QComboBox()
        self._reference.addItem(_("Selection"), "selection")
        self._reference.addItem(_("Artboard"), "artboard")
        self._reference.setToolTip(_("A single object is always aligned to the artboard"))
        self._reference.activated.connect(
            lambda index: align.set_align_reference(session, self._reference.itemData(index))
        )
        reference_row.addWidget(self._reference, 1)
        layout.addLayout(reference_row)
        layout.addStretch(1)

    @staticmethod
    def _buttons(command_ids: list[str], actions: AppActions, columns: int) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(2)
        for index, command_id in enumerate(command_ids):
            button = QToolButton()
            button.setDefaultAction(actions[command_id])
            button.setIconSize(_ICON_SIZE)
            button.setAutoRaise(True)
            grid.addWidget(button, index // columns, index % columns)
        return grid

    def refresh(self, state: AppState) -> None:
        index = self._reference.findData(state.align_reference)
        if self._reference.currentIndex() != index:
            self._reference.blockSignals(True)
            self._reference.setCurrentIndex(index)
            self._reference.blockSignals(False)
