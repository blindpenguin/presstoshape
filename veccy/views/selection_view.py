from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QFrame, QLabel, QLineEdit, QVBoxLayout, QWidget

from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState
from veccy.models.shapes import EllipseShape, PathShape, RectShape, Shape, Style, TextShape
from veccy.views.style_editor import FILL, STROKE, WIDTH, StyleEditor

_COORD_RANGE = 100_000.0

# (field, label, minimum) per shape kind; minimum None = coordinate (may be negative).
_GEOMETRY: dict[type, tuple[tuple[str, str, float | None], ...]] = {
    RectShape: (("x", "X", None), ("y", "Y", None), ("width", "W", 0.1), ("height", "H", 0.1)),
    EllipseShape: (("cx", "Center X", None), ("cy", "Center Y", None), ("rx", "Radius X", 0.1), ("ry", "Radius Y", 0.1)),
    TextShape: (("x", "X", None), ("y", "Y", None), ("font_size", "Size", 1.0)),
}

_KIND_NAMES = {RectShape: "Rectangle", EllipseShape: "Ellipse", PathShape: "Path", TextShape: "Text"}

_HINT = "Click to select, Ctrl+click to add or remove, drag on empty canvas for box select."


class SelectionOptions(QWidget):
    """Select tool page: geometry of a single selected shape, plus style of the whole selection."""

    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self._controller = controller
        self._shape: Shape | None = None

        layout = QVBoxLayout(self)
        self._heading = QLabel()
        heading_font = self._heading.font()
        heading_font.setBold(True)
        self._heading.setFont(heading_font)
        layout.addWidget(self._heading)

        self._hint = QLabel(_HINT)
        self._hint.setWordWrap(True)
        self._hint.setEnabled(False)
        layout.addWidget(self._hint)

        geometry = QWidget()
        self._form = QFormLayout(geometry)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._text = QLineEdit()
        self._text.editingFinished.connect(self._on_text_edited)
        self._form.addRow("Text", self._text)
        # One spinbox per field name; rows are shown/hidden per shape kind (x/y shared by rect and text).
        self._spins: dict[str, QDoubleSpinBox] = {}
        for rows in _GEOMETRY.values():
            for field, label, minimum in rows:
                if field in self._spins:
                    continue
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(-_COORD_RANGE if minimum is None else minimum, _COORD_RANGE)
                spin.valueChanged.connect(lambda v, f=field: self._on_spin(f, v))
                self._spins[field] = spin
                self._form.addRow(label, spin)
        layout.addWidget(geometry)
        self._geometry = geometry

        self._separator = QFrame()
        self._separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(self._separator)

        self._style = StyleEditor(
            (FILL, STROKE, WIDTH),
            on_fill=controller.set_fill,
            on_stroke=controller.set_stroke,
            on_width=controller.set_stroke_width,
        )
        layout.addWidget(self._style)
        layout.addStretch(1)

    def refresh(self, state: AppState) -> None:
        selected = self._controller.selected_shapes()
        single = selected[0] if len(selected) == 1 else None
        self._shape = single

        if not selected:
            self._heading.setText("Nothing selected")
        elif single is not None:
            self._heading.setText(_KIND_NAMES[type(single)])
        else:
            self._heading.setText(f"{len(selected)} objects")
        self._hint.setVisible(not selected)
        self._style.setVisible(bool(selected))
        self._style.refresh(selected[0].style if selected else Style())

        rows = _GEOMETRY.get(type(single), ())
        self._geometry.setVisible(bool(rows))
        self._separator.setVisible(bool(rows))
        fields = {field for field, _, _ in rows}
        for field, spin in self._spins.items():
            self._form.setRowVisible(spin, field in fields)
            if field in fields:
                value = getattr(single, field)
                if spin.value() != value:
                    spin.blockSignals(True)
                    spin.setValue(value)
                    spin.blockSignals(False)
        is_text = isinstance(single, TextShape)
        self._form.setRowVisible(self._text, is_text)
        if is_text and not self._text.hasFocus() and self._text.text() != single.text:
            self._text.setText(single.text)

    def _on_spin(self, field: str, value: float) -> None:
        if self._shape is not None:
            self._controller.set_shape_field(self._shape.id, field, value)

    def _on_text_edited(self) -> None:
        if isinstance(self._shape, TextShape):
            self._controller.set_shape_field(self._shape.id, "text", self._text.text())
            # A rejected (empty) edit leaves the model unchanged; show its text again.
            if self._shape is not None and isinstance(self._shape, TextShape):
                current = self._controller.find_shape(self._shape.id)
                if isinstance(current, TextShape):
                    self._text.setText(current.text)
