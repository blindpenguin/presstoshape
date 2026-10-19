from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QSlider, QStackedWidget, QVBoxLayout, QWidget

from presstoshape.editing import containers
from presstoshape.editing.operations import composites, view
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.models.app_state import AppState, Tool
from presstoshape.views.selection_view import SelectionOptions
from presstoshape.views.style_editor import FILL, STROKE, WIDTH, StyleEditor
from presstoshape.views.unit_fields import LengthSpinBox, font_unit
from presstoshape.views.widgets import PartModeBox

_FIELDS = {
    Tool.RECTANGLE: (FILL, STROKE, WIDTH),
    Tool.ELLIPSE: (FILL, STROKE, WIDTH),
    Tool.PEN: (STROKE, WIDTH, FILL),
    Tool.PENCIL: (STROKE, WIDTH, FILL),
    Tool.TEXT: (FILL,),
}

_HINTS = {
    Tool.NODE: N_(
        "Click a path to edit its nodes. Drag nodes or their handles; Shift+click or drag a box to select "
        "several. Alt+drag a handle to break a smooth node. Double-click a segment to add a node, "
        "Delete removes selected nodes."
    ),
    Tool.RECTANGLE: N_("Drag to draw. Shift: square."),
    Tool.ELLIPSE: N_("Drag to draw. Shift: circle."),
    Tool.PEN: N_("Click to add points.\nDouble-click / Enter: finish.\nEsc: cancel."),
    Tool.PENCIL: N_(
        "Drag to draw. Smoothing: how calm the line comes out, from following your hand closely to flowing "
        "curves with few nodes. End near the start to close the shape."
    ),
    Tool.TEXT: N_("Click on the canvas to place text."),
}

TITLES = {
    Tool.SELECT: N_("Selection"),
    Tool.NODE: N_("Node tool"),
    Tool.PEN: N_("Pen tool"),
    Tool.PENCIL: N_("Pencil tool"),
    Tool.RECTANGLE: N_("Rectangle tool"),
    Tool.ELLIPSE: N_("Ellipse tool"),
    Tool.TEXT: N_("Text tool"),
}


class ToolOptionsPanel(QStackedWidget):
    """One page per tool: the selection's properties for Select, the new-shape style for drawing tools."""

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._selection = SelectionOptions(session)
        self.addWidget(self._selection)
        self._pages: dict[Tool, QWidget] = {Tool.SELECT: self._selection}
        self._editors: dict[Tool, StyleEditor] = {}
        self._font_size: LengthSpinBox | None = None
        self._smoothing: QSlider | None = None
        self._smoothing_value: QLabel | None = None
        # Drawing tools show the mode new parts get while a Composite is being edited.
        self._part_modes: dict[Tool, tuple[QFormLayout, PartModeBox]] = {}
        self._pages[Tool.NODE] = self._hint_page(_(_HINTS[Tool.NODE]))
        for tool, fields in _FIELDS.items():
            editor = StyleEditor(
                fields,
                on_fill=lambda color, t=tool: view.set_tool_style(session, t, fill=color),
                on_stroke=lambda color, t=tool: view.set_tool_style(session, t, stroke=color),
                on_width=lambda width, t=tool: view.set_tool_style(session, t, stroke_width=width),
            )
            if tool is not Tool.TEXT:
                part_mode = PartModeBox()
                part_mode.mode_picked.connect(partial(composites.set_new_part_mode, session))
                editor.form.addRow(_("New part"), part_mode)
                self._part_modes[tool] = (editor.form, part_mode)
            if tool is Tool.PENCIL:
                editor.form.addRow(_("Smoothing"), self._smoothing_row(session))
            if tool is Tool.TEXT:
                self._font_size = LengthSpinBox(1, 999)
                self._font_size.px_changed.connect(partial(view.set_font_size, session))
                editor.form.addRow(_("Size"), self._font_size)

            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(editor)
            hint = QLabel(_(_HINTS[tool]))
            hint.setWordWrap(True)
            hint.setEnabled(False)
            layout.addSpacing(8)
            layout.addWidget(hint)
            layout.addStretch(1)
            self.addWidget(page)
            self._pages[tool] = page
            self._editors[tool] = editor

    def _smoothing_row(self, session: Session) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        self._smoothing = QSlider(Qt.Orientation.Horizontal)
        self._smoothing.setRange(0, 100)
        self._smoothing.valueChanged.connect(partial(view.set_pencil_smoothing, session))
        self._smoothing_value = QLabel()
        self._smoothing_value.setMinimumWidth(24)
        layout.addWidget(self._smoothing, 1)
        layout.addWidget(self._smoothing_value)
        return row

    def _hint_page(self, text: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel(text)
        hint.setWordWrap(True)
        hint.setEnabled(False)
        layout.addWidget(hint)
        layout.addStretch(1)
        self.addWidget(page)
        return page

    def refresh(self, state: AppState) -> None:
        tool = state.active_tool
        self.setCurrentWidget(self._pages[tool])
        if tool is Tool.SELECT:
            self._selection.refresh(state)
            return
        if tool is Tool.NODE:
            return
        document = state.document
        self._editors[tool].set_unit(document.unit, document.dpi)
        self._editors[tool].refresh(state.tool_styles[tool])
        if tool in self._part_modes:
            form, part_mode = self._part_modes[tool]
            editing = containers.editing(state)
            form.setRowVisible(part_mode, editing)
            if editing:
                part_mode.show_mode(state.new_part_mode)
        if tool is Tool.PENCIL and self._smoothing is not None and self._smoothing_value is not None:
            self._smoothing.blockSignals(True)
            self._smoothing.setValue(state.pencil_smoothing)
            self._smoothing.blockSignals(False)
            self._smoothing_value.setText(str(state.pencil_smoothing))
        if tool is Tool.TEXT and self._font_size is not None:
            self._font_size.set_unit(font_unit(document), document.dpi)
            self._font_size.set_px(state.font_size)
