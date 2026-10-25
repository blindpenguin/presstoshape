import json
from dataclasses import replace

import pytest

from presstoshape.editing import containers
from presstoshape.editing.operations import composites, edit_mode, groups, layers, selection, shapes, view
from presstoshape.formats.p2s import decode_document, encode_document
from presstoshape.formats.svg import read_svg, write_svg
from presstoshape.geometry import nodes
from presstoshape.models.app_state import Tool
from presstoshape.models.layout import GridSettings
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, PathShape
from presstoshape.tools.base import CursorType, Mods
from tests.helpers import all_shapes, drag, setup_tools

NONE = Mods()
SHIFT = Mods(shift=True)
ALT = Mods(alt=True)
CTRL = Mods(ctrl=True)


def _pen():
    session, g = setup_tools()
    session.state.snapping = replace(session.state.snapping, enabled=False)
    g.set_tool(Tool.PEN)
    return session, g


def _click(g, point, mods=NONE):
    g.press(point, mods)
    g.release(point, mods)


def _clicks(g, *points):
    for point in points:
        _click(g, point)


def _path(session) -> PathShape:
    (path,) = all_shapes(session)
    assert isinstance(path, PathShape)
    return path


def test_clicks_make_a_straight_polygon_selected_in_one_undo_step():
    session, g = _pen()
    depth = session.undo_count
    _clicks(g, (0, 0), (100, 0), (100, 100))
    assert g.key("enter")
    path = _path(session)
    assert path.segments == (MoveTo(0, 0), LineTo(100, 0), LineTo(100, 100))
    assert path.style == session.state.tool_styles[Tool.PEN]
    assert session.state.selection == {path.id}
    assert session.undo_count == depth + 1 and session.undo_label == "Add path"


def test_a_press_that_barely_moves_is_a_click():
    session, g = _pen()
    _click(g, (0, 0))
    g.press((100, 0), NONE)
    g.move((102, 1), NONE)
    g.release((102, 1), NONE)
    g.key("enter")
    assert _path(session).segments == (MoveTo(0, 0), LineTo(100, 0))


def test_drag_pulls_out_mirrored_handles_and_the_node_is_smooth():
    session, g = _pen()
    _click(g, (0, 0))
    drag(g, (100, 0), (130, 20))
    _click(g, (200, 0))
    g.key("enter")
    segments = _path(session).segments
    assert segments[1] == CubicTo(0, 0, 70, -20, 100, 0)
    assert segments[2] == CubicTo(130, 20, 200, 0, 200, 0)
    assert nodes.nodes(segments)[1].smooth


def test_alt_while_dragging_breaks_the_handles_and_releasing_alt_mirrors_again():
    session, g = _pen()
    _click(g, (0, 0))
    g.press((100, 0), NONE)
    g.move((130, 0), NONE)
    g.move((100, 40), ALT)
    assert g.overlay.nodes[0].handles == (((100, 0), (70, 0)), ((100, 0), (100, 40)))
    g.release((100, 40), ALT)
    _click(g, (200, 0))
    g.key("enter")
    segments = _path(session).segments
    assert (segments[1].c2x, segments[1].c2y) == (70, 0)
    assert (segments[2].c1x, segments[2].c1y) == (100, 40)
    assert not nodes.nodes(segments)[1].smooth

    session, g = _pen()
    _click(g, (0, 0))
    g.press((100, 0), NONE)
    g.move((100, 40), ALT)
    g.move((130, 0), NONE)
    g.release((130, 0), NONE)
    _click(g, (200, 0))
    g.key("enter")
    assert nodes.nodes(_path(session).segments)[1].smooth


def test_shift_constrains_segments_and_handles_to_45_degrees():
    session, g = _pen()
    _click(g, (0, 0))
    _click(g, (100, 7), SHIFT)
    drag(g, (200, 0), (230, 4), shift=True)
    g.key("enter")
    segments = _path(session).segments
    assert segments[1] == LineTo(100, 0)
    assert segments[2].c2x == pytest.approx(170) and segments[2].c2y == pytest.approx(0)


def test_clicking_the_first_node_closes_a_straight_path_without_a_duplicate_node():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0), (100, 100))
    assert g.hover((2, 1)) is CursorType.PEN_CLOSE
    g.move((2, 1), NONE)
    assert isinstance(g.overlay.preview[0][-1], Close)
    assert g.overlay.nodes[0].selected == {0}
    _click(g, (2, 1))
    segments = _path(session).segments
    assert segments == (MoveTo(0, 0), LineTo(100, 0), LineTo(100, 100), Close())
    assert len(nodes.nodes(segments)) == 3
    assert not g.active


def test_dragging_on_the_first_node_shapes_the_closing_curve():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0), (100, 100))
    drag(g, (0, 0), (0, -30))
    segments = _path(session).segments
    assert segments[1] == CubicTo(0, -30, 100, 0, 100, 0)
    assert segments[-2] == CubicTo(100, 100, 0, 30, 0, 0) and isinstance(segments[-1], Close)
    infos = nodes.nodes(segments)
    assert len(infos) == 3 and infos[0].smooth


def test_alt_drag_on_the_first_node_keeps_the_first_segment():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0), (100, 100))
    drag(g, (0, 0), (0, -30), alt=True)
    segments = _path(session).segments
    assert segments[1] == LineTo(100, 0)
    assert segments[-2] == CubicTo(100, 100, 0, 30, 0, 0)


def test_closing_needs_two_nodes_and_the_first_node_beats_snapping():
    session, g = setup_tools()
    g.set_tool(Tool.PEN)
    _click(g, (100, 100))
    assert g.hover((100, 100)) is CursorType.PEN_ADD
    # The path's own first node is a snap target too, but a press there must close, not add a node.
    _clicks(g, (300, 100), (300, 300))
    _click(g, (103, 101))
    assert isinstance(_path(session).segments[-1], Close)


def test_enter_and_double_click_finish_open_without_an_extra_node():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0))
    g.double_click((100, 0), NONE)
    g.release((100, 0), NONE)
    assert _path(session).segments == (MoveTo(0, 0), LineTo(100, 0))
    assert not g.active


def test_double_click_when_idle_starts_nothing():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0), (100, 100), (0, 0))
    g.double_click((0, 0), NONE)
    g.release((0, 0), NONE)
    assert len(all_shapes(session)) == 1 and not g.active


def test_escape_discards_the_path():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0))
    g.escape()
    assert all_shapes(session) == [] and not g.active and g.overlay.preview is None


def test_backspace_removes_the_last_node_and_ends_on_the_only_one():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0), (100, 100))
    assert g.key("backspace")
    g.key("enter")
    assert _path(session).segments == (MoveTo(0, 0), LineTo(100, 0))
    session, g = _pen()
    _click(g, (0, 0))
    assert g.key("backspace")
    assert not g.active and not g.key("backspace")


def test_switching_tools_commits_the_open_path_or_drops_a_single_node():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0))
    g.set_tool(Tool.SELECT)
    assert _path(session).segments == (MoveTo(0, 0), LineTo(100, 0))
    session, g = _pen()
    _click(g, (0, 0))
    g.set_tool(Tool.SELECT)
    g.set_tool(Tool.PEN)
    assert all_shapes(session) == [] and not g.active


def test_a_click_on_the_last_node_is_ignored():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0), (101, 1))
    g.key("enter")
    assert len(_path(session).segments) == 2


def test_nodes_snap_to_the_grid_and_to_earlier_nodes_ctrl_ignores_it():
    session, g = setup_tools()
    session.state.document.grid = GridSettings(50, 2)
    view.set_snap_target(session, "grid", True)
    view.toggle_grid(session)
    g.set_tool(Tool.PEN)
    _click(g, (48, 3))
    _click(g, (152, 98), CTRL)
    g.key("enter")
    assert _path(session).segments == (MoveTo(50, 0), LineTo(152, 98))

    session, g = setup_tools()
    g.set_tool(Tool.PEN)
    _clicks(g, (333, 333), (377, 211), (421, 333))
    _click(g, (379, 213))
    g.key("enter")
    assert _path(session).segments[-1] == LineTo(377, 211)


def test_hover_shows_rubber_band_and_snap_hits_but_dragging_does_not_snap():
    session, g = setup_tools()
    shapes.add_rectangle(session, (500, 500), (600, 600))
    g.set_tool(Tool.PEN)
    _click(g, (0, 0))
    g.move((80, 40), NONE)
    assert g.overlay.preview[0] == (MoveTo(0, 0), LineTo(80, 40))
    assert g.hover((80, 40)) is CursorType.PEN_ADD
    g.press((300, 300), NONE)
    g.move((498, 502), NONE)
    assert g.overlay.snap == ()
    assert g.overlay.nodes[0].handles[-1] == ((300, 300), (498, 502))


def test_idle_hover_is_a_crosshair():
    session, g = _pen()
    assert g.hover((0, 0)) is CursorType.CROSS


def test_inside_a_group_the_path_is_added_there():
    session, g = _pen()
    a = shapes.add_rectangle(session, (0, 0), (10, 10))
    b = shapes.add_rectangle(session, (20, 20), (30, 30))
    selection.set_selection(session, {a, b})
    groups.group(session)
    (group,) = session.state.selection
    edit_mode.enter(session, group)
    _clicks(g, (100, 100), (200, 100))
    g.key("enter")
    assert len(containers.pickable_shapes(session.state)) == 3


def test_inside_a_composite_the_path_becomes_a_part():
    session, g = _pen()
    bottom = shapes.add_rectangle(session, (0, 0), (400, 400))
    top = shapes.add_rectangle(session, (50, 50), (150, 150))
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session)
    (composite,) = session.state.selection
    edit_mode.enter(session, composite)
    _clicks(g, (100, 100), (300, 100), (300, 300), (100, 100))
    assert len(containers.edited_composite(session.state).parts) == 3


def test_hidden_layer_refuses_with_a_message():
    session, g = _pen()
    layers.set_layer_visible(session, 0, False)
    _clicks(g, (0, 0), (100, 0))
    g.key("enter")
    assert all_shapes(session) == [] and "hidden" in session.state.status_message
    assert not g.active


def test_closed_pen_path_round_trips_through_svg_and_p2s():
    session, g = _pen()
    _clicks(g, (0, 0), (100, 0))
    drag(g, (100, 100), (60, 120))
    drag(g, (0, 0), (0, -30))
    document = session.state.document
    path = _path(session)
    assert decode_document(json.loads(json.dumps(encode_document(document)))).layers[0].shapes[0] == path
    reread = [s for layer in read_svg(write_svg(document)).layers for s in layer.shapes][0]
    assert reread.segments == path.segments
