from functools import partial

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from presstoshape import icons
from presstoshape.editing import containers, queries
from presstoshape.editing.operations import composites, shapes, style, transform
from presstoshape.editing.session import Session
from presstoshape.geometry import transforms
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.app_state import AppState, Document
from presstoshape.models.shapes import (
    CompositeShape,
    EllipseShape,
    GroupShape,
    PathShape,
    RectShape,
    Shape,
    Style,
    TextAnchor,
    TextShape,
)
from presstoshape.render.paths import PathCache
from presstoshape.views.icon_engine import icon
from presstoshape.views.style_editor import ALL_FIELDS, StyleEditor
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
    # The group's bounds, set through transform.set_bounds.
    GroupShape: (("x", N_("X"), None), ("y", N_("Y"), None), ("width", N_("W"), 0.1), ("height", N_("H"), 0.1)),
}

_TYPE_NAMES = {
    RectShape: N_("Rectangle"),
    EllipseShape: N_("Ellipse"),
    PathShape: N_("Path"),
    TextShape: N_("Text"),
    CompositeShape: N_("Composite"),
    GroupShape: N_("Group"),
}

_HINT = N_(
    "Click to select, Ctrl+click to add or remove, drag on empty canvas for box select. "
    "Drag handles to scale (Shift keeps proportions, Alt scales from the centre); "
    "drag just outside a corner to rotate (Shift snaps to 15°)."
)
_ROTATABLE = (RectShape, EllipseShape, TextShape)
# One below 0 is the "mixed" placeholder of the corner radius (special value text shows at the minimum).
_MIXED_RADIUS = -1.0


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
        self._radius = LengthSpinBox(_MIXED_RADIUS, _COORD_RANGE)
        self._radius.setSpecialValueText(_("Mixed"))
        self._radius.px_changed.connect(self._on_radius)
        self._form.addRow(_("Corner radius"), self._radius)
        self._anchor_row, self._anchor_buttons = self._anchor_buttons_row()
        self._form.addRow(_("Alignment"), self._anchor_row)
        layout.addWidget(geometry_box)
        self._geometry = geometry_box

        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self._separator)

        self._style = StyleEditor(ALL_FIELDS, lambda changes: style.set_style(session, **changes))
        layout.addWidget(self._style)
        layout.addStretch(1)

    def _anchor_buttons_row(self) -> tuple[QWidget, dict[TextAnchor, QToolButton]]:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        buttons: dict[TextAnchor, QToolButton] = {}
        for anchor, path, tooltip in (
            ("start", icons.ALIGN_START, _("Left: the text starts at its position")),
            ("middle", icons.ALIGN_MIDDLE, _("Centre: the text is centred on its position")),
            ("end", icons.ALIGN_END, _("Right: the text ends at its position")),
        ):
            button = QToolButton()
            button.setIcon(icon(path))
            button.setIconSize(QSize(18, 18))
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda _checked=False, value=anchor: self._on_anchor(value))
            layout.addWidget(button)
            buttons[anchor] = button
        layout.addStretch(1)
        return row, buttons

    def refresh(self, state: AppState) -> None:
        selected = queries.selected_shapes(self._session.state)
        single = selected[0] if len(selected) == 1 else None
        self._shape = single

        if not selected:
            self._heading.setText(_("Nothing selected"))
        elif single is not None:
            if isinstance(single, GroupShape):
                count = len(single.children)
                self._heading.setText(
                    ngettext("Group of {count} object", "Group of {count} objects", count).format(count=count)
                )
            else:
                self._heading.setText(_(_TYPE_NAMES[type(single)]))
        else:
            count = len(selected)
            self._heading.setText(ngettext("{count} object", "{count} objects", count).format(count=count))
        self._hint.setVisible(not selected)
        self._style.setVisible(bool(selected))
        document = state.document
        self._style.set_unit(document.unit, document.dpi)
        fill_rule_matters = any(_has_open_fill_rule(shape) for shape in selected)
        self._style.refresh(style.display_style(selected[0]) if selected else Style(), fill_rule_matters)

        rows = _GEOMETRY.get(type(single), ())
        show_mode = self._refresh_mode(state, selected)
        show_radius = self._refresh_radius(selected, document)
        show_anchor = self._refresh_anchor(selected)
        has_geometry = bool(rows) or show_mode or show_radius or show_anchor
        self._geometry.setVisible(has_geometry)
        self._separator.setVisible(has_geometry)
        fields = {row[0] for row in rows}
        for field, spin in self._spins.items():
            spin.set_unit(font_unit(document) if field == "font_size" else document.unit, document.dpi)
            self._form.setRowVisible(spin, field in fields)
            if field in fields:
                spin.set_px(_field_value(single, field))
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

    def _refresh_radius(self, selected: list[Shape], document: Document) -> bool:
        """Corner radius when only rectangles are selected; "Mixed" when their radii differ."""
        visible = bool(selected) and all(isinstance(shape, RectShape) for shape in selected)
        self._form.setRowVisible(self._radius, visible)
        if visible:
            self._radius.set_unit(document.unit, document.dpi)
            radii = {radius for rect in selected for radius in (rect.rx, rect.ry)}
            self._radius.set_px(radii.pop() if len(radii) == 1 else _MIXED_RADIUS)
        return visible

    def _refresh_anchor(self, selected: list[Shape]) -> bool:
        """Alignment buttons when only text is selected; none checked when the texts differ."""
        visible = bool(selected) and all(isinstance(shape, TextShape) for shape in selected)
        self._form.setRowVisible(self._anchor_row, visible)
        if visible:
            anchors = {shape.anchor for shape in selected}
            for anchor, button in self._anchor_buttons.items():
                button.setChecked(anchors == {anchor})
        return visible

    def _on_radius(self, px: float) -> None:
        if px > _MIXED_RADIUS:
            shapes.set_corner_radius(self._session, px)

    def _on_anchor(self, anchor: TextAnchor) -> None:
        shapes.set_text_anchor(self._session, anchor)
        # Unchanged anchors make no edit and no refresh; undo the button's own toggle.
        self.refresh(self._session.state)

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
        if isinstance(self._shape, GroupShape):
            transform.set_bounds(self._session, self._shape.id, field, value)
        elif self._shape is not None:
            shapes.set_shape_field(self._session, self._shape.id, field, value)

    def _on_text_edited(self) -> None:
        if isinstance(self._shape, TextShape):
            shapes.set_shape_field(self._session, self._shape.id, "text", self._text.text())
            # A rejected (empty) edit leaves the model unchanged; show its text again.
            if self._shape is not None and isinstance(self._shape, TextShape):
                current = queries.find_shape(self._session.state, self._shape.id)
                if isinstance(current, TextShape):
                    self._text.setText(current.text)


def _has_open_fill_rule(shape: Shape) -> bool:
    """Whether the fill rule can change how `shape` looks: paths and Composites, also inside groups."""
    if isinstance(shape, GroupShape):
        return any(_has_open_fill_rule(child) for child in shape.children)
    return isinstance(shape, (PathShape, CompositeShape))


def _field_value(shape: Shape, field: str) -> float:
    """A geometry field of `shape`; for a group, its bounds."""
    if isinstance(shape, GroupShape):
        box = PathCache().geometry_bounds(shape)
        return {"x": box.left(), "y": box.top(), "width": box.width(), "height": box.height()}[field]
    return getattr(shape, field)
