"""Number fields for lengths: the model keeps document pixels, the field shows the document's unit."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDoubleSpinBox

from presstoshape.geometry import units
from presstoshape.models.app_state import Document, Unit

_STEPS: dict[Unit, float] = {"px": 1.0, "mm": 1.0, "cm": 0.1, "in": 0.1, "pt": 1.0}


def font_unit(document: Document) -> Unit:
    """Type is measured in points in physical documents; px documents keep pixels."""
    return "pt" if units.is_physical(document.unit) else "px"


class LengthSpinBox(QDoubleSpinBox):
    """Shows a length kept in document pixels in a display unit; `px_changed` reports user edits in pixels."""

    px_changed = Signal(float)

    def __init__(self, minimum_px: float, maximum_px: float, fine: bool = False) -> None:
        super().__init__()
        self._minimum_px, self._maximum_px = minimum_px, maximum_px
        self._fine = fine
        self._unit: Unit = "px"
        self._dpi = 96.0
        self._configure()
        self.valueChanged.connect(lambda _value: self.px_changed.emit(self.px()))

    def set_unit(self, unit: Unit, dpi: float) -> None:
        if (unit, dpi) == (self._unit, self._dpi):
            return
        px = self.px()
        self._unit, self._dpi = unit, dpi
        self._configure()
        self.set_px(px)

    def _configure(self) -> None:
        self.blockSignals(True)
        self.setDecimals(units.DECIMALS[self._unit])
        # px fields look as they always did; physical units say which one they are.
        self.setSuffix(f" {self._unit}" if units.is_physical(self._unit) else "")
        self.setSingleStep(_STEPS[self._unit] / (2 if self._fine else 1))
        self.setRange(self._shown(self._minimum_px), self._shown(self._maximum_px))
        self.blockSignals(False)

    def _shown(self, px: float) -> float:
        return units.from_px(px, self._unit, self._dpi)

    def px(self) -> float:
        return units.to_px(self.value(), self._unit, self._dpi)

    def set_px(self, px: float) -> None:
        """Shows `px` without emitting; values that already round to the shown one are left alone."""
        shown = self._shown(px)
        if abs(self.value() - shown) < 0.5 * 10 ** -self.decimals():
            return
        self.blockSignals(True)
        self.setValue(shown)
        self.blockSignals(False)
