from collections.abc import Callable, Sequence

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QWidget

from veccy.models.shapes import Style
from veccy.views.widgets import ColorButton

FILL, STROKE, WIDTH = "fill", "stroke", "width"


class _PaintRow(QWidget):
    """Checkbox (paint on/off) + swatch. Calls `on_change(hex | None)`."""

    def __init__(self, on_change: Callable[[str | None], None]) -> None:
        super().__init__()
        self.check, self.button = QCheckBox(), ColorButton()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.check)
        layout.addWidget(self.button, 1)
        self.check.toggled.connect(lambda on: on_change(self.button.color if on else None))
        self.button.color_picked.connect(on_change)

    def set_color(self, color: str | None) -> None:
        self.check.blockSignals(True)
        self.check.setChecked(color is not None)
        self.check.blockSignals(False)
        self.button.setEnabled(color is not None)
        # Keep the last swatch color when paint is off, so re-enabling restores it.
        if color is not None:
            self.button.set_color(color)


class StyleEditor(QWidget):
    """Form for a subset of Style fields. Emits plain callbacks; refresh(style) never calls them."""

    def __init__(
        self,
        fields: Sequence[str],
        *,
        on_fill: Callable[[str | None], None],
        on_stroke: Callable[[str | None], None],
        on_width: Callable[[float], None],
    ) -> None:
        super().__init__()
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self._fill = self._stroke = None
        self._width: QDoubleSpinBox | None = None
        for f in fields:
            if f == FILL:
                self._fill = _PaintRow(on_fill)
                self.form.addRow("Fill", self._fill)
            elif f == STROKE:
                self._stroke = _PaintRow(on_stroke)
                self.form.addRow("Stroke", self._stroke)
            elif f == WIDTH:
                self._width = QDoubleSpinBox()
                self._width.setRange(0, 200)
                self._width.setSingleStep(0.5)
                self._width.setDecimals(2)
                self._width.valueChanged.connect(on_width)
                self.form.addRow("Width", self._width)

    def refresh(self, style: Style) -> None:
        if self._fill is not None:
            self._fill.set_color(style.fill)
        if self._stroke is not None:
            self._stroke.set_color(style.stroke)
        if self._width is not None:
            self._width.blockSignals(True)
            if self._width.value() != style.stroke_width:
                self._width.setValue(style.stroke_width)
            self._width.blockSignals(False)
            self._width.setEnabled(style.stroke is not None)
