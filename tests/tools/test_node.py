import math

import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import composites, edit_mode, node_editing, selection, shapes, view
from presstoshape.editing.operations import corners as corner_ops
from presstoshape.geometry import nodes
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import CubicTo, LineTo, MoveTo, Rounding
from presstoshape.tools.base import CursorType, Mods
from tests.helpers import drag, setup_tools

NONE = Mods()


def _node_setup():
    session, g = setup_tools()
    sid = shapes.add_path(session, [(0, 0), (100, 0), (200, 100)])
    view.select_tool(session, Tool.NODE)
    g.set_tool(Tool.NODE)
    return session, g, sid


def test_node_click_selects_and_shift_toggles():
    session, g, sid = _node_setup()
    drag(g, (100, 0), (100, 0))
    assert session.state.node_selection == {(sid, 1)}
    drag(g, (200, 100), (200, 100), shift=True)
    assert session.state.node_selection == {(sid, 1), (sid, 2)}
    drag(g, (100, 0), (100, 0), shift=True)
    assert session.state.node_selection == {(sid, 2)}


def test_node_band_selects_nodes():
    session, g, sid = _node_setup()
    drag(g, (-10, -10), (150, 20))
    assert session.state.node_selection == {(sid, 0), (sid, 1)}


def test_node_drag_commits_one_move():
    session, g, sid = _node_setup()
    depth = session.undo_count
    g.press((100, 0), NONE)
    g.move((110, 20), NONE)
    (live,) = g.overlay.live
    assert (live.segments[1].x, live.segments[1].y) == (110, 20)
    assert queries.find_shape(session.state, sid).segments[1].x == 100
    g.release((110, 20), NONE)
    moved = queries.find_shape(session.state, sid).segments[1]
    assert (moved.x, moved.y) == (110, 20)
    assert session.undo_count == depth + 1


def test_selected_node_drags_even_with_retracted_handles():
    session, g = setup_tools()
    segments = (MoveTo(0, 0), CubicTo(0, 0, 100, 0, 100, 0), CubicTo(100, 0, 200, 100, 200, 100))
    sid = shapes.add_drawn_path(session, segments, Tool.PEN)
    view.select_tool(session, Tool.NODE)
    g.set_tool(Tool.NODE)
    drag(g, (100, 0), (100, 0))
    drag(g, (100, 0), (110, 20))
    moved = queries.find_shape(session.state, sid).segments[1]
    assert (moved.x, moved.y, moved.c2x, moved.c2y) == (110, 20, 110, 20)
    drag(g, (110, 20), (140, 20), alt=True)
    pulled = queries.find_shape(session.state, sid).segments
    assert (pulled[1].x, pulled[1].y) == (110, 20)
    assert (pulled[1].c2x, pulled[1].c2y) == (140, 20) or (pulled[2].c1x, pulled[2].c1y) == (140, 20)


def test_control_drag_keeps_smooth_unless_alt():
    session, g, sid = _node_setup()
    drag(g, (100, 0), (100, 0))
    path = queries.find_shape(session.state, sid)
    c2 = (path.segments[1].c2x, path.segments[1].c2y)
    drag(g, c2, (c2[0] - 10, c2[1] - 30))
    smooth = queries.find_shape(session.state, sid)
    assert smooth.segments[2] != path.segments[2]
    session.undo()
    node_editing.set_node_selection(session, {(sid, 1)})
    drag(g, c2, (c2[0] - 10, c2[1] - 30), alt=True)
    assert queries.find_shape(session.state, sid).segments[2] == path.segments[2]


def test_double_click_on_segment_inserts_node():
    session, g, sid = _node_setup()
    path = queries.find_shape(session.state, sid)
    on_curve = nodes._eval(path.segments, nodes.Topology(path.segments), 2, 0.5)
    g.double_click(on_curve, NONE)
    assert len(queries.find_shape(session.state, sid).segments) == len(path.segments) + 1
    assert session.state.node_selection == {(sid, 2)}


def test_node_escape_order():
    session, g, sid = _node_setup()
    drag(g, (100, 0), (100, 0))
    g.press((100, 0), NONE)
    g.move((120, 0), NONE)
    g.escape()
    assert g.overlay.live == () and queries.find_shape(session.state, sid).segments[1].x == 100
    assert session.state.node_selection == {(sid, 1)}
    g.escape()
    assert session.state.node_selection == frozenset() and session.state.selection == {sid}
    g.escape()
    assert session.state.selection == set()


def test_node_hover_types_and_hint_for_rect():
    session, g, sid = _node_setup()
    assert g.hover((100, 0)) is CursorType.NODE
    path = queries.find_shape(session.state, sid)
    on_curve = nodes._eval(path.segments, nodes.Topology(path.segments), 2, 0.5)
    assert g.hover(on_curve) is CursorType.NODE_INSERT
    assert g.hover((500, 500)) is CursorType.ARROW
    assert g.hint is None
    rect = shapes.add_rectangle(session, (300, 300), (350, 350))
    selection.set_selection(session, {rect})
    assert "Object to Path" in g.hint


def test_node_overlay_shows_controls_of_selected_nodes():
    session, g, sid = _node_setup()
    assert g.overlay.nodes[0].controls == frozenset()
    drag(g, (100, 0), (100, 0))
    (overlay,) = g.overlay.nodes
    assert overlay.selected == {1}
    assert overlay.controls == {(1, 1), (1, 2), (2, 1), (2, 2)}


def test_node_tool_edits_a_path_part_inside_a_composite():
    session, g = setup_tools()
    path_id = shapes.add_path(session, [(0, 0), (100, 0), (200, 100)])
    rect = shapes.add_rectangle(session, (300, 300), (310, 310))
    selection.set_selection(session, {path_id, rect})
    composites.make_composite(session)
    (composite_id,) = session.state.selection
    edit_mode.enter(session, composite_id)
    selection.set_selection(session, {path_id})
    view.select_tool(session, Tool.NODE)
    g.set_tool(Tool.NODE)
    drag(g, (100, 0), (100, 0))
    drag(g, (100, 0), (110, 20))
    part = queries.find_shape(session.state, composite_id).parts[0]
    assert (part.segments[1].x, part.segments[1].y) == (110, 20)


def test_arrow_keys_nudge_selected_nodes_or_else_the_paths():
    session, g, sid = _node_setup()
    selection.set_selection(session, {sid})
    assert g.nudge(1, 0, NONE)
    assert queries.find_shape(session.state, sid).segments[0].x == 1
    drag(g, (100, 0), (100, 0))
    assert g.nudge(0, 1, Mods(shift=True))
    path = queries.find_shape(session.state, sid)
    assert (path.segments[1].x, path.segments[1].y) == (101, 10)
    assert session.undo_label == "Nudge nodes"


def test_arrow_keys_with_alt_move_one_screen_pixel_and_report_nothing_to_move():
    session, g, sid = _node_setup()
    g.pixel_size = 0.25
    selection.set_selection(session, {sid})
    g.nudge(-1, 0, Mods(alt=True))
    assert queries.find_shape(session.state, sid).segments[0].x == -0.25
    selection.set_selection(session, set())
    assert not g.nudge(1, 0, NONE)


def test_node_tool_cant_pick_a_locked_path():
    from dataclasses import replace

    session, g, sid = _node_setup()
    selection.set_selection(session, set())
    layer = session.state.document.layers[0]
    layer.shapes = [replace(shape, locked=True) for shape in layer.shapes]
    drag(g, (100, 0), (100, 0))
    assert session.state.selection == set() and session.state.node_selection == set()


# --- live-corner widgets ----------------------------------------------------------------


def _square_setup():
    session, g = setup_tools()
    sid = shapes.add_drawn_path(session, rect_segments(0, 0, 100, 100), Tool.PEN)
    selection.set_selection(session, {sid})
    view.select_tool(session, Tool.NODE)
    g.set_tool(Tool.NODE)
    return session, g, sid


def _widgets(g):
    (overlay,) = g.overlay.nodes
    return dict(overlay.widgets)


def test_widgets_for_all_corners_or_only_selected_ones():
    session, g, sid = _square_setup()
    assert set(_widgets(g)) == {0, 1, 2, 3}
    node_editing.set_node_selection(session, {(sid, 2)})
    assert set(_widgets(g)) == {2}
    # Inside the corner, 12 screen px along the bisector.
    (x, y) = _widgets(g)[2]
    assert math.dist((x, y), (100, 100)) == pytest.approx(12)
    assert x < 100 and y < 100


def test_no_widgets_on_open_ends_smooth_or_tiny_corners():
    session, g, sid = _node_setup()
    # A smooth spline: no corners to round.
    assert set(_widgets(g)) == set()
    open_sid = shapes.add_drawn_path(session, ((MoveTo(0, 0), LineTo(100, 0), LineTo(100, 100))), Tool.PEN)
    selection.set_selection(session, {open_sid})
    assert set(_widgets(g)) == {1}
    session2, g2, sid2 = _square_setup()
    g2.pixel_size = 30.0
    assert set(_widgets(g2)) == set()


def test_dragging_a_widget_rounds_the_selected_corners_in_one_step():
    session, g, sid = _square_setup()
    node_editing.set_node_selection(session, {(sid, 1), (sid, 2)})
    depth = session.undo_count
    start = _widgets(g)[2]
    assert g.hover(start) is CursorType.CORNER
    g.press(start, NONE)
    # Pull 10 px further along the bisector: the arc middle moves by 10, so r = 10 / (sqrt(2) - 1).
    end = (start[0] - 10 / math.sqrt(2), start[1] - 10 / math.sqrt(2))
    g.move(end, NONE)
    live = {shape.id: shape for shape in g.overlay.live}
    assert live[sid].segments[2].rounding.radius == pytest.approx(10 / (math.sqrt(2) - 1))
    g.release(end, NONE)
    segments = queries.find_shape(session.state, sid).segments
    assert segments[1].rounding == segments[2].rounding == Rounding(pytest.approx(10 / (math.sqrt(2) - 1)))
    assert segments[0].rounding is None
    assert session.undo_count == depth + 1 and session.undo_label == "Round corners"


def test_pressing_a_widget_without_moving_changes_nothing():
    session, g, sid = _square_setup()
    depth = session.undo_count
    start = _widgets(g)[2]
    g.press(start, NONE)
    g.move((start[0] + 0.0, start[1]), NONE)
    assert g.overlay.live[0].segments[2].rounding is None
    g.release(start, NONE)
    assert session.undo_count == depth


def test_dragging_back_into_the_node_removes_the_rounding():
    session, g, sid = _square_setup()
    corner_ops.set_radius(session, {(sid, 2)}, 30)
    start = _widgets(g)[2]
    drag(g, start, (100, 100))
    assert queries.find_shape(session.state, sid).segments[2].rounding is None


def test_nodes_win_over_widgets_and_widgets_over_segments():
    session, g, sid = _square_setup()
    g.pixel_size = 0.2
    assert g.hover((100, 100)) is CursorType.NODE
    position = _widgets(g)[2]
    assert g.hover(position) is CursorType.CORNER


def test_widgets_hide_while_dragging_nodes():
    session, g, sid = _square_setup()
    g.press((0, 0), NONE)
    g.move((5, 5), NONE)
    (overlay,) = g.overlay.nodes
    assert overlay.widgets == ()
    g.release((5, 5), NONE)


def test_double_click_on_a_widget_asks_for_exact_values():
    session, g, sid = _square_setup()
    asked = []
    g.toolbox.context.edit_corners = asked.append
    node_editing.set_node_selection(session, {(sid, 0)})
    position = _widgets(g)[0]
    g.double_click(position, NONE)
    assert asked == [{(sid, 0)}]
    depth = session.undo_count
    assert len(queries.find_shape(session.state, sid).segments) == 5 and session.undo_count == depth


def test_limited_corners_are_reported():
    session, g, sid = _square_setup()
    corner_ops.set_radius(session, {(sid, 1), (sid, 2)}, 80)
    (overlay,) = g.overlay.nodes
    assert overlay.limited == {1, 2}
