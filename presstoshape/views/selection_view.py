from functools import partial

from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QFrame, QLabel, QLineEdit, QVBoxLayout, QWidget

from presstoshape.editing import containers, queries
from presstoshape.editing.operations import composites, shapes, style, transform
from presstoshape.editing.session import Session
from presstoshape.geometry import transforms
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.app_state import AppState
from presstoshape.models.shapes import CompositeShape, EllipseShape, PathShape, RectShape, Shape, Style, TextShape
from presstoshape.views.style_editor import FILL, STROKE, WIDTH, StyleEditor
from presstoshape.views.unit_fields import LengthSpinBox, font_unit
from presstoshape.views.widgets import PartModeBox

_COORD_RANGE = 100_000.0

# (field, label, minimum) per shape type; minimum None = coordinate (may be negative).
_GEOMETRY: dict[type, tuple[tuple[str, str, float | None], ...]] = {
    RectShape: (("x", N_("X"), None), ("y", N_("Y"), None), ("width", N_("W"), 0.1), ("height", N_("H"), 0.1)),
    EllipseShape: (
        ("cx", N_("Centre X"), None),
        ("cy", N_("Centre Y"), None),
        ("rx", N_("Radius X"), 0.1),
        ("ry", N_("Radius Y"), 0.1),
    ),
    TextShape: (("x", N_("X"), None), ("y", N_("Y"), None), ("font_size", N_("Size"), 1.0)),
}

_TYPE_NAMES = {
    RectShape: N_("Rectangle"),
    EllipseShape: N_("Ellipse"),
    PathShape: N_("Path"),
    TextShape: N_("Text"),
    CompositeShape: N_("Composite"),
}

_HINT = N_(
    "Click to select, Ctrl+click to add or remove, drag on empty canvas for box select. "
    "Drag handles to scale (Shift keeps proportions, Alt scales from the centre); "
    "drag just outside a corner to rotate (Shift snaps to 15°)."
)
_ROTATABLE = (RectShape, EllipseShape, TextShape)


class SelectionOptions(QWidget):
    """Select tool page: geometry of a single selected shape, plus style of the whole selection."""

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session
        self._shape: Shape | None = None

        layout = QVBoxLayout(self)
        self._heading = QLabel()
        heading_font = self._heading.font()
        heading_font.setBold(True)
        self._heading.setFont(heading_font)
        layout.addWidget(self._heading)

        self._hint = QLabel(_(_HINT))
        self._hint.setWordWrap(True)
        self._hint.setEnabled(False)
        layout.addWidget(self._hint)

        geometry_box = QWidget()
        self._form = QFormLayout(geometry_box)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._mode = PartModeBox()
        self._mode.mode_picked.connect(partial(composites.set_part_mode, session))
        self._form.addRow(_("Mode"), self._mode)
        self._text = QLineEdit()
        self._text.editingFinished.connect(self._on_text_edited)
        self._form.addRow(_("Text"), self._text)
        # One spinbox per field name; rows are shown/hidden per shape type (x/y shared by rect and text).
        self._spins: dict[str, LengthSpinBox] = {}
        for rows in _GEOMETRY.values():
            for field, label, minimum in rows:
                if field in self._spins:
                    continue
                spin = LengthSpinBox(-_COORD_RANGE if minimum is None else minimum, _COORD_RANGE)
                spin.px_changed.connect(lambda px, f=field: self._on_spin(f, px))
                self._spins[field] = spin
                self._form.addRow(_(label), spin)
        self._rotation = QDoubleSpinBox()
        self._rotation.setDecimals(1)
        # One below -180 is the "skewed" placeholder (special value text shows at the minimum).
        self._rotation.setRange(-180.1, 180.0)
        self._rotation.setSuffix("°")
        self._rotation.valueChanged.connect(self._on_rotation)
        self._form.addRow(_("Rotation"), self._rotation)
        layout.addWidget(geometry_box)
        self._geometry = geometry_box

        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self._separator)

        self._style = StyleEditor(
            (FILL, STROKE, WIDTH),
            on_fill=partial(style.set_fill, session),
            on_stroke=partial(style.set_stroke, session),
            on_width=partial(style.set_stroke_width, session),
        )
        layout.addWidget(self._style)
        layout.addStretch(1)

    def refresh(self, state: AppState) -> None:
        selected = queries.selected_shapes(self._session.state)
        single = selected[0] if len(selected) == 1 else None
        self._shape = single

        if not selected:
            self._heading.setText(_("Nothing selected"))
        elif single is not None:
            self._heading.setText(_(_TYPE_NAMES[type(single)]))
        else:
            count = len(selected)
            self._heading.setText(ngettext("{count} object", "{count} objects", count).format(count=count))
        self._hint.setVisible(not selected)
        self._style.setVisible(bool(selected))
        document = state.document
        self._style.set_unit(document.unit, document.dpi)
        self._style.refresh(selected[0].style if selected else Style())

        rows = _GEOMETRY.get(type(single), ())
        show_mode = self._refresh_mode(state, selected)
        self._geometry.setVisible(bool(rows) or show_mode)
        self._separator.setVisible(bool(rows) or show_mode)
        fields = {row[0] for row in rows}
        for field, spin in self._spins.items():
            spin.set_unit(font_unit(document) if field == "font_size" else document.unit, document.dpi)
            self._form.setRowVisible(spin, field in fields)
            if field in fields:
                spin.set_px(getattr(single, field))
        self._refresh_rotation(single)
        is_text = isinstance(single, TextShape)
        self._form.setRowVisible(self._text, is_text)
        if is_text and not self._text.hasFocus() and self._text.text() != single.text:
            self._text.setText(single.text)

    def _refresh_mode(self, state: AppState, selected: list[Shape]) -> bool:
        """Part mode of the selection inside a Composite: its mode, "Base" or "Mixed". False outside edit mode."""
        composite = containers.edited_composite(state)
        visible = composite is not None and bool(selected)
        self._form.setRowVisible(self._mode, visible)
        if not visible:
            return False
        base_id = composite.parts[0].id
        others = {
            mode
            for part, mode in zip(composite.parts, composite.modes)
            if part.id in state.selection and part.id != base_id
        }
        if not others:
            self._mode.show_mode(None, _("Base"))
        elif len(others) == 1:
            self._mode.show_mode(next(iter(others)))
        else:
            self._mode.show_mode(None, _("Mixed"))
        self._mode.setEnabled(bool(others))
        return True

    def _refresh_rotation(self, single: Shape | None) -> None:
        rotatable = isinstance(single, _ROTATABLE)
        self._form.setRowVisible(self._rotation, rotatable)
        if not rotatable:
            return
        angle = transforms.rotation_of(single)
        skewed = angle is None
        self._rotation.setEnabled(not skewed)
        self._rotation.setSpecialValueText(_("skewed") if skewed else "")
        value = self._rotation.minimum() if skewed else angle
        if self._rotation.value() != value:
            self._rotation.blockSignals(True)
            self._rotation.setValue(value)
            self._rotation.blockSignals(False)

    def _on_rotation(self, value: float) -> None:
        if self._shape is None or value < -180:
            return
        transform.set_rotation(self._session, self._shape.id, value)

    def _on_spin(self, field: str, value: float) -> None:
        if self._shape is not None:
            shapes.set_shape_field(self._session, self._shape.id, field, value)

    def _on_text_edited(self) -> None:
        if isinstance(self._shape, TextShape):
            shapes.set_shape_field(self._session, self._shape.id, "text", self._text.text())
            # A rejected (empty) edit leaves the model unchanged; show its text again.
            if self._shape is not None and isinstance(self._shape, TextShape):
                current = queries.find_shape(self._session.state, self._shape.id)
                if isinstance(current, TextShape):
                    self._text.setText(current.text)
