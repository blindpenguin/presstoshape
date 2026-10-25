from PySide6.QtWidgets import QApplication, QWidget

from presstoshape.editing.operations import view
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool
from presstoshape.views.actions import AppActions
from presstoshape.views.tool_options_view import ToolOptionsPanel


def test_pencil_smoothing_slider_follows_and_sets_the_state():
    QApplication.instance() or QApplication([])
    session = Session()
    actions = AppActions(QWidget(), session, {})
    panel = ToolOptionsPanel(session, actions)
    session.subscribe(lambda: panel.refresh(session.state))
    view.select_tool(session, Tool.PENCIL)
    assert panel._smoothing.value() == 50 and panel._smoothing_value.text() == "50"
    panel._smoothing.setValue(70)
    assert session.state.pencil_smoothing == 70 and panel._smoothing_value.text() == "70"
    view.set_pencil_smoothing(session, 20)
    assert panel._smoothing.value() == 20


def test_corner_row_follows_selected_corners_and_edits_them():
    from presstoshape.editing import queries
    from presstoshape.editing.operations import corners, node_editing, selection, shapes
    from presstoshape.geometry.segments import rect_segments
    from presstoshape.models.shapes import Rounding

    QApplication.instance() or QApplication([])
    session = Session()
    actions = AppActions(QWidget(), session, {})
    panel = ToolOptionsPanel(session, actions)
    session.subscribe(lambda: panel.refresh(session.state))
    sid = shapes.add_drawn_path(session, rect_segments(0, 0, 100, 100), Tool.PEN)
    selection.set_selection(session, {sid})
    view.select_tool(session, Tool.NODE)
    assert not panel._corner_radius.isEnabled()
    node_editing.set_node_selection(session, {(sid, 0), (sid, 1)})
    assert panel._corner_radius.isEnabled() and panel._corner_radius.px() == 0
    depth = session.undo_count
    panel._corner_radius.setValue(5)
    panel._corner_radius.setValue(6)
    segments = queries.find_shape(session.state, sid).segments
    assert segments[0].rounding == segments[1].rounding == Rounding(6)
    assert session.undo_count == depth + 1
    panel._corner_kind.activated.emit(2)
    assert queries.find_shape(session.state, sid).segments[1].rounding == Rounding(6, "chamfer")
    corners.set_radius(session, {(sid, 0)}, 9)
    assert panel._corner_radius.specialValueText() and panel._corner_radius.px() < 0
    assert panel._corner_kind.currentIndex() == 2
