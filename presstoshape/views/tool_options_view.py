from functools import partial

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from presstoshape.editing import containers
from presstoshape.editing.operations import composites, view
from presstoshape.editing.operations import corners as corner_ops
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _
from presstoshape.models.app_state import AppState, Tool
from presstoshape.models.shapes import CORNER_KINDS
from presstoshape.views.actions import AppActions
from presstoshape.views.corner_dialog import kind_box
from presstoshape.views.keymap import NODE_STRUCTURE_IDS, NODE_TYPE_IDS, SUBPATH_IDS
from presstoshape.views.selection_view import SelectionOptions
from presstoshape.views.style_editor import FILL, FILL_RULE, OPACITY, STROKE, STROKE_OPTIONS, WIDTH, StyleEditor
from presstoshape.views.unit_fields import LengthSpinBox, font_unit
from presstoshape.views.widgets import PartModeBox

_ICON_SIZE = QSize(20, 20)
# The corner radius field shows "Mixed" at this value, below any real radius.
_MIXED_RADIUS = -1.0
_MAX_CORNER_PX = 100_000.0

_FIELDS = {
    Tool.RECTANGLE: (FILL, STROKE, WIDTH, OPACITY, STROKE_OPTIONS),
    Tool.ELLIPSE: (FILL, STROKE, WIDTH, OPACITY, STROKE_OPTIONS),
    Tool.PEN: (STROKE, WIDTH, FILL, OPACITY, FILL_RULE, STROKE_OPTIONS),
    Tool.PENCIL: (STROKE, WIDTH, FILL, OPACITY, FILL_RULE, STROKE_OPTIONS),
    Tool.TEXT: (FILL, OPACITY),
}

_HINTS = {
    Tool.NODE: N_(
        "Click a path to edit its nodes. Drag nodes or their handles; Shift+click or drag a box to select "
        "several. Alt+drag a handle to break a smooth node. Double-click a segment to add a node, "
        "Delete removes selected nodes. Corner nodes are diamonds, smooth ones squares; the larger node marks where "
        "each path starts."
    ),
    Tool.RECTANGLE: N_("Drag to draw. Shift: square."),
    Tool.ELLIPSE: N_("Drag to draw. Shift: circle."),
    Tool.PEN: N_(
        "Click: corner point. Drag: curve. Click the first point to close.\n"
        "Start or end on the open end of a path to continue or join it.\n"
        "Double-click / Enter: finish. Backspace: remove the last point. Esc: cancel.\n"
        "Shift: 45° steps. Alt while dragging: break the handles."
    ),
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

    def __init__(self, session: Session, actions: AppActions) -> None:
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
        self._pages[Tool.NODE] = self._node_page(session, actions)
        for tool, fields in _FIELDS.items():
            editor = StyleEditor(fields, lambda changes, t=tool: view.set_tool_style(session, t, **changes))
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

    def _node_page(self, session: Session, actions: AppActions) -> QWidget:
        """The node and subpath commands as buttons sharing the menu's actions, the selected corners' live-corner
        kind and radius, and the gesture hint."""
        page = QWidget()
        layout = QVBoxLayout(page)
        for command_ids in (NODE_TYPE_IDS, NODE_STRUCTURE_IDS, SUBPATH_IDS):
            grid = QGridLayout()
            grid.setSpacing(2)
            for index, command_id in enumerate(command_ids):
                button = QToolButton()
                button.setDefaultAction(actions[command_id])
                button.setIconSize(_ICON_SIZE)
                button.setAutoRaise(True)
                grid.addWidget(button, 0, index)
            grid.setColumnStretch(len(command_ids), 1)
            layout.addLayout(grid)
        form = QFormLayout()
        self._corner_kind = kind_box()
        self._corner_kind.activated.connect(
            lambda index: corner_ops.set_kind(
                session, corner_ops.selected_corners(session.state), self._corner_kind.itemData(index)
            )
        )
        self._corner_radius = LengthSpinBox(_MIXED_RADIUS, _MAX_CORNER_PX)
        self._corner_radius.setSpecialValueText(_("Mixed"))
        self._corner_radius.px_changed.connect(partial(self._on_corner_radius, session))
        form.addRow(_("Corner"), self._corner_kind)
        form.addRow(_("Radius"), self._corner_radius)
        layout.addLayout(form)
        hint = QLabel(_(_HINTS[Tool.NODE]))
        hint.setWordWrap(True)
        hint.setEnabled(False)
        layout.addSpacing(8)
        layout.addWidget(hint)
        layout.addStretch(1)
        self.addWidget(page)
        return page

    def _on_corner_radius(self, session: Session, px: float) -> None:
        if px > _MIXED_RADIUS:
            corner_ops.set_radius(session, corner_ops.selected_corners(session.state), px, merge_key="corner_radius")

    def _refresh_corners(self, state: AppState) -> None:
        values = corner_ops.selected_corner_values(state)
        self._corner_kind.setEnabled(values is not None)
        self._corner_radius.setEnabled(values is not None)
        kind, radius = values if values is not None else (None, 0.0)
        self._corner_kind.blockSignals(True)
        self._corner_kind.setCurrentIndex(CORNER_KINDS.index(kind) if kind is not None else -1)
        self._corner_kind.blockSignals(False)
        self._corner_radius.set_unit(state.document.unit, state.document.dpi)
        self._corner_radius.set_px(radius if radius is not None else _MIXED_RADIUS)

    def refresh(self, state: AppState) -> None:
        tool = state.active_tool
        self.setCurrentWidget(self._pages[tool])
        if tool is Tool.SELECT:
            self._selection.refresh(state)
            return
        if tool is Tool.NODE:
            self._refresh_corners(state)
            return
        document = state.document
        self._editors[tool].set_unit(document.unit, document.dpi)
        self._editors[tool].refresh(state.tool_styles[tool])
        if tool in self._part_modes:
            form, part_mode = self._part_modes[tool]
            in_composite = containers.edited_composite(state) is not None
            form.setRowVisible(part_mode, in_composite)
            if in_composite:
                part_mode.show_mode(state.new_part_mode)
        if tool is Tool.PENCIL and self._smoothing is not None and self._smoothing_value is not None:
            self._smoothing.blockSignals(True)
            self._smoothing.setValue(state.pencil_smoothing)
            self._smoothing.blockSignals(False)
            self._smoothing_value.setText(str(state.pencil_smoothing))
        if tool is Tool.TEXT and self._font_size is not None:
            self._font_size.set_unit(font_unit(document), document.dpi)
            self._font_size.set_px(state.font_size)
