from collections.abc import Callable, Sequence

from PySide6.QtWidgets import QCheckBox, QFormLayout, QHBoxLayout, QWidget

from presstoshape.i18n import _, pgettext
from presstoshape.models.app_state import Unit
from presstoshape.models.shapes import Style
from presstoshape.views.unit_fields import LengthSpinBox
from presstoshape.views.widgets import ColorButton

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
        self._width: LengthSpinBox | None = None
        for f in fields:
            if f == FILL:
                self._fill = _PaintRow(on_fill)
                self.form.addRow(_("Fill"), self._fill)
            elif f == STROKE:
                self._stroke = _PaintRow(on_stroke)
                self.form.addRow(_("Stroke"), self._stroke)
            elif f == WIDTH:
                self._width = LengthSpinBox(0, 200, fine=True)
                self._width.px_changed.connect(on_width)
                self.form.addRow(pgettext("stroke", "Width"), self._width)

    def set_unit(self, unit: Unit, dpi: float) -> None:
        """Unit the stroke width is shown in (the document's)."""
        if self._width is not None:
            self._width.set_unit(unit, dpi)

    def refresh(self, style: Style) -> None:
        if self._fill is not None:
            self._fill.set_color(style.fill)
        if self._stroke is not None:
            self._stroke.set_color(style.stroke)
        if self._width is not None:
            self._width.set_px(style.stroke_width)
            self._width.setEnabled(style.stroke is not None)
