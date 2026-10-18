from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QComboBox, QPushButton

from presstoshape.editing.operations.composites import MODE_LABELS


class ColorButton(QPushButton):
    """Swatch button that opens a color dialog. Emits `color_picked(hex)`; `set_color` doesn't emit."""

    color_picked = Signal(str)

    def __init__(self, color: str = "#000000") -> None:
        super().__init__()
        self.setFixedHeight(24)
        self.color = color
        self.set_color(color)
        self.clicked.connect(self._pick)

    def set_color(self, color: str) -> None:
        self.color = color
        self.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 1px solid #52525b; border-radius: 3px; }}"
            "QPushButton:disabled { background: #3f3f46; }"
        )

    def _pick(self) -> None:
        picked = QColorDialog.getColor(QColor(self.color), self.window())
        if picked.isValid():
            self.set_color(picked.name())
            self.color_picked.emit(picked.name())


class PartModeBox(QComboBox):
    """Composite part modes. Emits `mode_picked(mode)` on user changes; `show_mode` doesn't emit.

    `show_mode(None, text)` shows a non-selectable placeholder such as "Base" or "Mixed".
    """

    mode_picked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        for mode, label in MODE_LABELS.items():
            self.addItem(label, mode)
        self._placeholder = -1
        self.activated.connect(self._on_activated)

    def show_mode(self, mode: str | None, placeholder: str = "") -> None:
        self.blockSignals(True)
        if self._placeholder >= 0:
            self.removeItem(self._placeholder)
            self._placeholder = -1
        if mode is None:
            self.addItem(placeholder, None)
            self._placeholder = self.count() - 1
            self.setCurrentIndex(self._placeholder)
        else:
            self.setCurrentIndex(self.findData(mode))
        self.blockSignals(False)

    def _on_activated(self, index: int) -> None:
        mode = self.itemData(index)
        if mode is not None:
            self.mode_picked.emit(mode)
