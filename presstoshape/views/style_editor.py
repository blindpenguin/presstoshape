import re
from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSlider,
    QSpinBox,
    QWidget,
)

from presstoshape.geometry import units
from presstoshape.i18n import _, pgettext
from presstoshape.models.app_state import Unit
from presstoshape.models.shapes import Style
from presstoshape.views.unit_fields import LengthSpinBox
from presstoshape.views.widgets import ColorButton

FILL, STROKE, WIDTH, OPACITY, FILL_RULE, STROKE_OPTIONS = (
    "fill",
    "stroke",
    "width",
    "opacity",
    "fill_rule",
    "stroke_options",
)
ALL_FIELDS = (FILL, STROKE, WIDTH, OPACITY, FILL_RULE, STROKE_OPTIONS)

_DASH_SEPARATORS = re.compile(r"[\s,;]+")

OnChange = Callable[[dict[str, Any]], None]


def _percent_box() -> QSpinBox:
    box = QSpinBox()
    box.setRange(0, 100)
    box.setSuffix(" %")
    # Compact: the panel is narrow and some languages have long labels. Typing and the mouse wheel still work.
    box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    box.setAlignment(Qt.AlignmentFlag.AlignRight)
    box.setMinimumWidth(box.sizeHint().width())
    return box


def _show_value(widget: QSpinBox | QDoubleSpinBox | QSlider, value: float) -> None:
    if widget.value() != value:
        widget.blockSignals(True)
        widget.setValue(value)
        widget.blockSignals(False)


class _PaintRow(QWidget):
    """Checkbox (paint on/off) + swatch + paint opacity. Calls `on_color(hex | None)` and
    `on_opacity(0..1)`."""

    def __init__(self, on_color: Callable[[str | None], None], on_opacity: Callable[[float], None]) -> None:
        super().__init__()
        self.check, self.button, self.opacity = QCheckBox(), ColorButton(), _percent_box()
        self.button.setMinimumWidth(24)
        self.opacity.setToolTip(_("Opacity of this paint"))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.check)
        layout.addWidget(self.button, 1)
        layout.addWidget(self.opacity)
        self.check.toggled.connect(lambda on: on_color(self.button.color if on else None))
        self.button.color_picked.connect(on_color)
        self.opacity.valueChanged.connect(lambda value: on_opacity(value / 100))

    def set_paint(self, color: str | None, opacity: float) -> None:
        self.check.blockSignals(True)
        self.check.setChecked(color is not None)
        self.check.blockSignals(False)
        self.button.setEnabled(color is not None)
        self.opacity.setEnabled(color is not None)
        _show_value(self.opacity, round(opacity * 100))
        # Keep the last swatch color when paint is off, so re-enabling restores it.
        if color is not None:
            self.button.set_color(color)


class _OpacityRow(QWidget):
    """Slider and percent box for the object's opacity, kept in step."""

    def __init__(self, on_opacity: Callable[[float], None]) -> None:
        super().__init__()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.box = _percent_box()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.box)
        self.slider.valueChanged.connect(lambda value: on_opacity(value / 100))
        self.box.valueChanged.connect(lambda value: on_opacity(value / 100))

    def set_opacity(self, opacity: float) -> None:
        percent = round(opacity * 100)
        _show_value(self.slider, percent)
        _show_value(self.box, percent)


class _ChoiceBox(QComboBox):
    """Fixed choices as (value, text); calls `on_pick(value)` on user changes only."""

    def __init__(self, choices: Sequence[tuple[str, str]], on_pick: Callable[[str], None]) -> None:
        super().__init__()
        for value, text in choices:
            self.addItem(text, value)
        self.activated.connect(lambda index: on_pick(self.itemData(index)))

    def show_value(self, value: str) -> None:
        self.blockSignals(True)
        self.setCurrentIndex(max(0, self.findData(value)))
        self.blockSignals(False)


class StyleEditor(QWidget):
    """Form for a subset of Style fields. Edits call `on_change({field: value})`; refresh(style) never does."""

    def __init__(self, fields: Sequence[str], on_change: OnChange) -> None:
        super().__init__()
        self._on_change = on_change
        self._unit: Unit = "px"
        self._dpi = 96.0
        self._dashes: tuple[float, ...] = ()
        self.form = QFormLayout(self)
        self.form.setContentsMargins(0, 0, 0, 0)
        self._fill = self._stroke = self._opacity = None
        self._width: LengthSpinBox | None = None
        self._fill_rule = self._cap = self._join = None
        self._miter: QDoubleSpinBox | None = None
        self._dash_edit: QLineEdit | None = None
        self._dash_offset: LengthSpinBox | None = None
        for field in fields:
            if field == FILL:
                self._fill = _PaintRow(self._emitter("fill"), self._emitter("fill_opacity"))
                self.form.addRow(_("Fill"), self._fill)
            elif field == STROKE:
                self._stroke = _PaintRow(self._emitter("stroke"), self._emitter("stroke_opacity"))
                self.form.addRow(_("Stroke"), self._stroke)
            elif field == WIDTH:
                self._width = LengthSpinBox(0, 200, fine=True)
                self._width.px_changed.connect(self._emitter("stroke_width"))
                self.form.addRow(pgettext("stroke", "Width"), self._width)
            elif field == OPACITY:
                self._opacity = _OpacityRow(self._emitter("opacity"))
                self.form.addRow(_("Opacity"), self._opacity)
            elif field == FILL_RULE:
                rules = (("nonzero", pgettext("fill rule", "Nonzero")), ("evenodd", pgettext("fill rule", "Even-odd")))
                self._fill_rule = _ChoiceBox(rules, self._emitter("fill_rule"))
                self._fill_rule.setToolTip(_("Even-odd leaves overlapping parts of a shape open as holes"))
                self.form.addRow(_("Fill rule"), self._fill_rule)
            elif field == STROKE_OPTIONS:
                self._add_stroke_options()

    def _add_stroke_options(self) -> None:
        caps = (
            ("butt", pgettext("line cap", "Butt")),
            ("round", pgettext("line cap", "Round")),
            ("square", pgettext("line cap", "Square")),
        )
        joins = (
            ("miter", pgettext("line join", "Mitre")),
            ("round", pgettext("line join", "Round")),
            ("bevel", pgettext("line join", "Bevel")),
        )
        self._cap = _ChoiceBox(caps, self._emitter("cap"))
        self._cap.setToolTip(
            _(
                "How open line ends look: Butt stops at the end point, Round and Square reach half the stroke width "
                "past it"
            )
        )
        self.form.addRow(pgettext("stroke", "Cap"), self._cap)
        self._join = _ChoiceBox(joins, self._emitter("join"))
        self._join.setToolTip(
            _(
                "How the stroke turns at sharp corners. It changes only the stroke's outer edge, so it shows on thick "
                "strokes; to round a rectangle itself, use Corner radius"
            )
        )
        self.form.addRow(pgettext("stroke", "Join"), self._join)
        self._miter = QDoubleSpinBox()
        self._miter.setRange(1, 100)
        self._miter.setDecimals(1)
        self._miter.setToolTip(
            _(
                "At very sharp angles a mitre join becomes a long spike. Past this length (in stroke widths) the corner "
                "is bevelled instead. At 4 that only happens below about 29°, so most corners don't change"
            )
        )
        self._miter.valueChanged.connect(self._emitter("miter_limit"))
        self.form.addRow(_("Mitre limit"), self._miter)
        self._dash_edit = QLineEdit()
        self._dash_edit.setPlaceholderText(_("Solid"))
        self._dash_edit.setToolTip(_("Dash and gap lengths, for example 4 2"))
        self._dash_edit.editingFinished.connect(self._on_dashes_edited)
        self.form.addRow(_("Dashes"), self._dash_edit)
        self._dash_offset = LengthSpinBox(-10_000, 10_000, fine=True)
        self._dash_offset.px_changed.connect(self._emitter("dash_offset"))
        self.form.addRow(_("Dash offset"), self._dash_offset)

    def _emitter(self, field: str) -> Callable[[Any], None]:
        return lambda value: self._on_change({field: value})

    def set_unit(self, unit: Unit, dpi: float) -> None:
        """Unit lengths are shown in (the document's)."""
        self._unit, self._dpi = unit, dpi
        for box in (self._width, self._dash_offset):
            if box is not None:
                box.set_unit(unit, dpi)
        self._show_dashes()

    def refresh(self, style: Style, fill_rule_matters: bool = True) -> None:
        """`fill_rule_matters`: False for shapes whose outline can't overlap itself (rectangles, ellipses,
        text), where the fill rule row would only confuse."""
        stroked = style.stroke is not None
        if self._fill is not None:
            self._fill.set_paint(style.fill, style.fill_opacity)
        if self._stroke is not None:
            self._stroke.set_paint(style.stroke, style.stroke_opacity)
        if self._width is not None:
            self._width.set_px(style.stroke_width)
            self._width.setEnabled(stroked)
        if self._opacity is not None:
            self._opacity.set_opacity(style.opacity)
        if self._fill_rule is not None:
            self._fill_rule.show_value(style.fill_rule)
            self.form.setRowVisible(self._fill_rule, fill_rule_matters and style.fill is not None)
        if self._cap is not None and self._join is not None and self._miter is not None:
            self._cap.show_value(style.cap)
            self._join.show_value(style.join)
            _show_value(self._miter, style.miter_limit)
            self._dash_offset.set_px(style.dash_offset)
            for row in (self._cap, self._join, self._dash_edit, self._dash_offset):
                self.form.setRowVisible(row, stroked)
            self.form.setRowVisible(self._miter, stroked and style.join == "miter")
            self.form.setRowVisible(self._dash_offset, stroked and bool(style.dashes))
            self._dashes = style.dashes
            self._show_dashes()

    def _show_dashes(self) -> None:
        if self._dash_edit is None or self._dash_edit.hasFocus():
            return
        decimals = units.DECIMALS[self._unit]
        shown = (units.from_px(value, self._unit, self._dpi) for value in self._dashes)
        text = " ".join(f"{value:.{decimals}f}".rstrip("0").rstrip(".") for value in shown)
        if self._dash_edit.text() != text:
            self._dash_edit.setText(text)

    def _on_dashes_edited(self) -> None:
        text = self._dash_edit.text().strip()
        try:
            values = tuple(float(item) for item in _DASH_SEPARATORS.split(text) if item)
        except ValueError:
            values = None
        if values is None:
            # Not numbers: show what the shape has again.
            self._dash_edit.clearFocus()
            self._show_dashes()
            return
        dashes = tuple(units.to_px(value, self._unit, self._dpi) for value in values)
        if dashes != self._dashes:
            self._on_change({"dashes": dashes})
