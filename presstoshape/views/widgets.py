from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QPushButton


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
