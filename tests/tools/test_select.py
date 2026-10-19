import math

import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import composites, selection, shapes, transform
from presstoshape.geometry import affine, transforms
from presstoshape.models.app_state import Tool
from presstoshape.tools.base import CursorType, Mods
from tests.helpers import all_shapes, drag, setup_tools

NONE = Mods()


def test_click_selects_and_empty_click_clears():
    session, g = setup_tools()
    sid = shapes.add_rectangle(session, (0, 0), (50, 50))
    selection.set_selection(session, set())
    drag(g, (25, 25), (25, 25))
    assert session.state.selection == {sid}
    drag(g, (200, 200), (200, 200))
    assert session.state.selection == set()


def test_ctrl_click_toggles():
    session, g = setup_tools()
    a = shapes.add_rectangle(session, (0, 0), (50, 50))
    b = shapes.add_rectangle(session, (100, 0), (150, 50))
    selection.set_selection(session, {a})
    drag(g, (125, 25), (125, 25), ctrl=True)
    assert session.state.selection == {a, b}
    drag(g, (25, 25), (25, 25), ctrl=True)
    assert session.state.selection == {b}


def test_drag_moves_selection_in_one_undo_step():
    session, g = setup_tools()
    sid = shapes.add_rectangle(session, (0, 0), (50, 50))
    undo_depth = session.undo_count
    g.press((25, 25), NONE)
    g.move((35, 45), NONE)
    assert g.overlay.moving == {sid} and g.overlay.matrix == affine.translation(10, 20)
    assert all_shapes(session)[0].x == 0
    g.release((35, 45), NONE)
    assert (all_shapes(session)[0].x, all_shapes(session)[0].y) == (10, 20)
    assert session.undo_count == undo_depth + 1


def test_rubber_band_selects_intersecting_and_ctrl_adds():
    session, g = setup_tools()
    a = shapes.add_rectangle(session, (0, 0), (50, 50))
    b = shapes.add_rectangle(session, (100, 100), (150, 150))
    selection.set_selection(session, set())
    g.press((-10, -10), NONE)
    g.move((60, 60), NONE)
    assert g.overlay.rubber_band == (-10, -10, 70, 70)
    assert g.overlay.selection == {a}
    g.release((60, 60), NONE)
    assert session.state.selection == {a}
    drag(g, (90, 90), (120, 120), ctrl=True)
    assert session.state.selection == {a, b}


def test_hover_move_over_shape_arrow_on_empty_canvas():
    session, g = setup_tools()
    shapes.add_rectangle(session, (0, 0), (50, 50))
    selection.set_selection(session, set())
    assert g.hover((25, 25)) is CursorType.MOVE
    assert g.hover((200, 200)) is CursorType.ARROW


def test_hover_keeps_press_cursor_during_drag():
    session, g = setup_tools()
    shapes.add_rectangle(session, (0, 0), (50, 50))
    g.press((25, 25), NONE)
    g.move((300, 300), NONE)
    assert g.hover((300, 300)) is CursorType.MOVE
    g.release((300, 300), NONE)


def _rect_selected(session, x0=100, y0=100, x1=200, y1=150):
    sid = shapes.add_rectangle(session, (x0, y0), (x1, y1))
    return sid


def test_se_corner_doubles_size_with_nw_fixed():
    session, g = setup_tools()
    sid = _rect_selected(session)
    drag(g, (200, 150), (300, 200))
    rect = queries.find_shape(session.state, sid)
    assert (rect.x, rect.y, rect.width, rect.height) == pytest.approx((100, 100, 200, 100))


def test_scale_is_one_undo_step_and_previews_live():
    session, g = setup_tools()
    sid = _rect_selected(session)
    undo_depth = session.undo_count
    g.press((200, 150), NONE)
    g.move((300, 200), NONE)
    assert queries.find_shape(session.state, sid).width == 100
    (live,) = g.overlay.live
    assert live.width == pytest.approx(200)
    assert g.overlay.frame.corners()[2] == pytest.approx((300, 200))
    g.release((300, 200), NONE)
    assert session.undo_count == undo_depth + 1


def test_edge_handle_scales_one_axis():
    session, g = setup_tools()
    sid = _rect_selected(session)
    drag(g, (200, 125), (250, 180))
    rect = queries.find_shape(session.state, sid)
    assert (rect.x, rect.y, rect.width, rect.height) == pytest.approx((100, 100, 150, 50))


def test_shift_corner_keeps_aspect_ratio():
    session, g = setup_tools()
    sid = _rect_selected(session)
    drag(g, (200, 150), (400, 160), shift=True)
    rect = queries.find_shape(session.state, sid)
    assert (rect.width, rect.height) == pytest.approx((300, 150))


def test_shift_edge_scales_uniformly():
    session, g = setup_tools()
    sid = _rect_selected(session)
    drag(g, (200, 125), (300, 125), shift=True)
    rect = queries.find_shape(session.state, sid)
    assert (rect.width, rect.height) == pytest.approx((200, 100))
    assert rect.y == pytest.approx(75)


def test_alt_scales_about_center():
    session, g = setup_tools()
    sid = _rect_selected(session)
    drag(g, (200, 150), (250, 175), alt=True)
    rect = queries.find_shape(session.state, sid)
    assert (rect.x, rect.y, rect.width, rect.height) == pytest.approx((50, 75, 200, 100))


def test_drag_past_opposite_edge_flips():
    session, g = setup_tools()
    sid = _rect_selected(session)
    drag(g, (200, 125), (50, 125))
    rect = queries.find_shape(session.state, sid)
    assert (rect.x, rect.width) == pytest.approx((50, 50))


def test_tiny_drag_clamps_to_one_screen_px():
    session, g = setup_tools()
    sid = _rect_selected(session)
    g.pixel_size = 0.5
    drag(g, (200, 125), (100, 125))
    assert queries.find_shape(session.state, sid).width == pytest.approx(0.5)


def test_rotated_rect_scales_along_own_axes():
    session, g = setup_tools()
    sid = _rect_selected(session)
    transform.set_rotation(session, sid, 90)
    # Rotated 90° about (150, 125): the shape's E edge midpoint is now at the bottom (150, 175).
    drag(g, (150, 175), (150, 225))
    rect = queries.find_shape(session.state, sid)
    assert (rect.width, rect.height) == pytest.approx((150, 50))
    assert transforms.rotation_of(rect) == pytest.approx(90)


def test_rotate_zone_rotates_about_frame_center():
    session, g = setup_tools()
    sid = _rect_selected(session, 100, 100, 200, 200)
    # NE rotate zone at (210, 90); rotating it to (210, 210) about (150, 150) sweeps 90°.
    g.press((210, 90), NONE)
    g.move((210, 210), NONE)
    assert g.hint == "Rotate 90.0°"
    g.release((210, 210), NONE)
    assert transforms.rotation_of(queries.find_shape(session.state, sid)) == pytest.approx(90)


def test_shift_rotation_snaps_to_15_degrees():
    session, g = setup_tools()
    sid = _rect_selected(session, 100, 100, 200, 120)
    # NE corner (200, 100), center (150, 110). Sweep about 40° snaps to 45°.
    cx, cy = 150, 110
    start = (210, 95)
    a0 = math.atan2(start[1] - cy, start[0] - cx)
    r = math.hypot(start[0] - cx, start[1] - cy)
    end = (cx + r * math.cos(a0 + math.radians(40)), cy + r * math.sin(a0 + math.radians(40)))
    drag(g, start, end, shift=True)
    assert transforms.rotation_of(queries.find_shape(session.state, sid)) == pytest.approx(45)


def test_escape_cancels_scale_without_undo_entry():
    session, g = setup_tools()
    sid = _rect_selected(session)
    undo_depth = session.undo_count
    g.press((200, 150), NONE)
    g.move((300, 200), NONE)
    g.escape()
    assert queries.find_shape(session.state, sid).width == 100
    assert session.undo_count == undo_depth
    assert session.state.selection == {sid}


def test_hover_over_handles():
    session, g = setup_tools()
    _rect_selected(session)
    assert g.hover((200, 125)) is CursorType.RESIZE_H
    assert g.hover((150, 100)) is CursorType.RESIZE_V
    assert g.hover((200, 150)) is CursorType.RESIZE_FDIAG
    assert g.hover((200, 100)) is CursorType.RESIZE_BDIAG
    assert g.hover((212, 88)) is CursorType.ROTATE


def test_hover_resize_follows_rotation():
    session, g = setup_tools()
    sid = _rect_selected(session)
    transform.set_rotation(session, sid, 90)
    assert g.hover((150, 175)) is CursorType.RESIZE_V


# --- composites ------------------------------------------------------------------------


def _composite_tool_session():
    session, g = setup_tools()
    bottom = shapes.add_rectangle(session, (100, 100), (200, 200))
    top = shapes.add_rectangle(session, (150, 150), (250, 250))
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session, "add")
    (composite_id,) = session.state.selection
    return session, g, composite_id, bottom, top


def test_double_click_enters_and_double_click_on_nothing_leaves():
    session, g, composite_id, bottom, top = _composite_tool_session()
    g.double_click((120, 120), NONE)
    assert session.state.edit_path == (composite_id,)
    g.double_click((400, 50), NONE)
    assert session.state.edit_path == () and session.state.selection == {composite_id}


def test_enter_key_enters_a_selected_composite():
    session, g, composite_id, bottom, top = _composite_tool_session()
    assert g.key("enter") is True
    assert session.state.edit_path == (composite_id,)


def test_escape_clears_selection_first_then_leaves():
    session, g, composite_id, bottom, top = _composite_tool_session()
    composites.enter(session, composite_id)
    selection.set_selection(session, {bottom})
    g.escape()
    assert session.state.selection == set() and session.state.edit_path == (composite_id,)
    g.escape()
    assert session.state.edit_path == ()


def test_dragging_a_part_moves_only_that_part():
    session, g, composite_id, bottom, top = _composite_tool_session()
    composites.enter(session, composite_id)
    g.press((240, 240), NONE)
    g.move((260, 240), NONE)
    assert g.overlay.moving == {top}
    g.release((260, 240), NONE)
    composite = queries.find_shape(session.state, composite_id)
    assert composite.parts[1].x == 170 and composite.parts[0].x == 100


def test_drawing_in_edit_mode_adds_a_part():
    session, g, composite_id, bottom, top = _composite_tool_session()
    composites.enter(session, composite_id)
    composites.set_new_part_mode(session, "subtract")
    g.set_tool(Tool.RECTANGLE)
    drag(g, (110, 110), (130, 130))
    composite = queries.find_shape(session.state, composite_id)
    assert len(composite.parts) == 3 and composite.modes[-1] == "subtract"


def test_nested_double_click_enters_one_level_deeper():
    session, g, composite_id, bottom, top = _composite_tool_session()
    composites.enter(session, composite_id)
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session)
    (nested_id,) = session.state.selection
    g.double_click((120, 120), NONE)
    assert session.state.edit_path == (composite_id, nested_id)


# --- Alt+drag duplicate ---------------------------------------------------------------------

ALT = Mods(alt=True)


def test_alt_drag_duplicates_and_moves_the_copy():
    session, g = setup_tools()
    sid = shapes.add_rectangle(session, (0, 0), (50, 50))
    selection.set_selection(session, set())
    undo_depth = session.undo_count
    g.press((25, 25), ALT)
    assert g.hover((25, 25)) is CursorType.DUPLICATE
    g.move((35, 45), ALT)
    overlay = g.overlay
    assert overlay.moving == frozenset() and [shape.id for shape in overlay.copies] == [sid]
    assert overlay.matrix == affine.translation(10, 20)
    g.release((35, 45), ALT)
    original, copy = all_shapes(session)
    assert (original.id, original.x, original.y) == (sid, 0, 0)
    assert (copy.x, copy.y) == (10, 20)
    assert session.state.selection == {copy.id}
    assert session.undo_count == undo_depth + 1 and session.undo_label == "Duplicate"
    assert g.overlay.copies == ()


def test_alt_click_without_movement_duplicates_nothing():
    session, g = setup_tools()
    shapes.add_rectangle(session, (0, 0), (50, 50))
    drag(g, (25, 25), (25, 25), alt=True)
    assert len(all_shapes(session)) == 1


def test_alt_drag_copies_the_whole_selection():
    session, g = setup_tools()
    a = shapes.add_rectangle(session, (0, 0), (50, 50))
    b = shapes.add_rectangle(session, (100, 0), (150, 50))
    selection.set_selection(session, {a, b})
    drag(g, (25, 25), (25, 125), alt=True)
    current = all_shapes(session)
    assert [shape.id for shape in current[:2]] == [a, b]
    assert [(shape.x, shape.y) for shape in current[2:]] == [(0, 100), (100, 100)]
