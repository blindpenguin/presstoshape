from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QPushButton

from presstoshape.editing.operations.composites import PART_MODES, mode_label
from presstoshape.i18n import _
from presstoshape.models.shapes import Gradient, GradientStop, flat_color


def _rgba(stop: GradientStop) -> str:
    color = QColor(stop.color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {round(stop.opacity * 255)})"


class ColorButton(QPushButton):
    """Swatch button showing a paint; a click is for the caller to handle (`clicked`). The colour itself is
    chosen in the Colour panel."""

    def __init__(self, color: str = "#000000") -> None:
        super().__init__()
        self.setFixedHeight(24)
        self.color = color
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self.color = color
        self.setToolTip(_("Edit in the Colour panel"))
        self._set_background(color)

    def set_gradient(self, gradient: Gradient) -> None:
        """Shows the gradient's stops as a strip; `color` becomes its first stop, where a colour pick starts."""
        self.color = flat_color(gradient) or self.color
        self.setToolTip(_("Gradient: picking a colour in the Colour panel replaces it"))
        stops = ", ".join(f"stop:{stop.offset:.3f} {_rgba(stop)}" for stop in gradient.stops)
        self._set_background(f"qlineargradient(x1:0, y1:0, x2:1, y2:0, {stops})")

    def _set_background(self, background: str) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background: {background}; border: 1px solid #52525b; border-radius: 3px; }}"
            "QPushButton:disabled { background: #3f3f46; }"
        )


class PartModeBox(QComboBox):
    """Composite part modes. Emits `mode_picked(mode)` on user changes; `show_mode` doesn't emit.

    `show_mode(None, text)` shows a non-selectable placeholder such as "Base" or "Mixed".
    """

    mode_picked = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        for mode in PART_MODES:
            self.addItem(mode_label(mode), mode)
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
