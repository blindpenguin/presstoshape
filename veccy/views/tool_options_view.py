from functools import partial

from PySide6.QtWidgets import QDoubleSpinBox, QLabel, QStackedWidget, QVBoxLayout, QWidget

from veccy.editing.operations import view
from veccy.editing.session import Session
from veccy.models.app_state import AppState, Tool
from veccy.views.selection_view import SelectionOptions
from veccy.views.style_editor import FILL, STROKE, WIDTH, StyleEditor

_FIELDS = {
    Tool.RECTANGLE: (FILL, STROKE, WIDTH),
    Tool.ELLIPSE: (FILL, STROKE, WIDTH),
    Tool.PEN: (STROKE, WIDTH, FILL),
    Tool.TEXT: (FILL,),
}

_HINTS = {
    Tool.NODE: (
        "Click a path to edit its nodes. Drag nodes or their handles; Shift+click or drag a box to select "
        "several. Alt+drag a handle to break a smooth node. Double-click a segment to add a node, "
        "Delete removes selected nodes."
    ),
    Tool.RECTANGLE: "Drag to draw. Shift: square.",
    Tool.ELLIPSE: "Drag to draw. Shift: circle.",
    Tool.PEN: "Click to add points.\nDouble-click / Enter: finish.\nEsc: cancel.",
    Tool.TEXT: "Click on the canvas to place text.",
}

TITLES = {
    Tool.SELECT: "Selection",
    Tool.NODE: "Node tool",
    Tool.PEN: "Pen tool",
    Tool.RECTANGLE: "Rectangle tool",
    Tool.ELLIPSE: "Ellipse tool",
    Tool.TEXT: "Text tool",
}


class ToolOptionsPanel(QStackedWidget):
    """One page per tool: the selection's properties for Select, the new-shape style for drawing tools."""

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._selection = SelectionOptions(session)
        self.addWidget(self._selection)
        self._pages: dict[Tool, QWidget] = {Tool.SELECT: self._selection}
        self._editors: dict[Tool, StyleEditor] = {}
        self._font_size: QDoubleSpinBox | None = None
        self._pages[Tool.NODE] = self._hint_page(_HINTS[Tool.NODE])
        for tool, fields in _FIELDS.items():
            editor = StyleEditor(
                fields,
                on_fill=lambda color, t=tool: view.set_tool_style(session, t, fill=color),
                on_stroke=lambda color, t=tool: view.set_tool_style(session, t, stroke=color),
                on_width=lambda width, t=tool: view.set_tool_style(session, t, stroke_width=width),
            )
            if tool is Tool.TEXT:
                self._font_size = QDoubleSpinBox()
                self._font_size.setRange(1, 999)
                self._font_size.setDecimals(1)
                self._font_size.valueChanged.connect(partial(view.set_font_size, session))
                editor.form.addRow("Size", self._font_size)

            page = QWidget()
            layout = QVBoxLayout(page)
            layout.addWidget(editor)
            hint = QLabel(_HINTS[tool])
            hint.setWordWrap(True)
            hint.setEnabled(False)
            layout.addSpacing(8)
            layout.addWidget(hint)
            layout.addStretch(1)
            self.addWidget(page)
            self._pages[tool] = page
            self._editors[tool] = editor

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
        self._editors[tool].refresh(state.tool_styles[tool])
        if tool is Tool.TEXT and self._font_size is not None:
            self._font_size.blockSignals(True)
            self._font_size.setValue(state.font_size)
            self._font_size.blockSignals(False)
