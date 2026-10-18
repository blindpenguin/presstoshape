import math

import pytest

from veccy.controllers import affine, geometry, nodes
from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState, Tool
from veccy.models.shapes import PathShape, RectShape
from veccy.render.paths import PathCache
from veccy.views.canvas_gestures import CanvasGestures
from veccy.views.gesture_types import CursorType, Mods, resize_cursor_type

NONE = Mods()


def _setup(text: str | None = "hi") -> tuple[AppController, CanvasGestures]:
    c = AppController(AppState())
    g = CanvasGestures(c, PathCache(), repaint=lambda: None, ask_text=lambda: text)
    g.set_state(c.state)
    c.subscribe(lambda: g.set_state(c.state))
    return c, g


def _shapes(c: AppController):
    return [s for layer in c.state.document.layers for s in layer.shapes]


def _drag(g: CanvasGestures, a, b, shift=False, ctrl=False, alt=False):
    mods = Mods(shift, ctrl, alt)
    g.press(a, mods)
    g.move(b, mods)
    g.release(b, mods)


def test_rectangle_drag_adds_shape_with_shift_square():
    c, g = _setup()
    g.set_tool(Tool.RECTANGLE)
    _drag(g, (10, 10), (50, 30), shift=True)
    rect = _shapes(c)[0]
    assert isinstance(rect, RectShape) and rect.width == rect.height == 40


def test_preview_follows_drag_and_clears_on_release():
    c, g = _setup()
    g.set_tool(Tool.ELLIPSE)
    g.press((0, 0), NONE)
    g.move((40, 20), NONE)
    assert g.overlay.preview is not None
    g.release((40, 20), NONE)
    assert g.overlay.preview is None


def test_click_selects_and_empty_click_clears():
    c, g = _setup()
    sid = c.add_rectangle((0, 0), (50, 50))
    c.set_selection(set())
    _drag(g, (25, 25), (25, 25))
    assert c.state.selection == {sid}
    _drag(g, (200, 200), (200, 200))
    assert c.state.selection == set()


def test_ctrl_click_toggles():
    c, g = _setup()
    a = c.add_rectangle((0, 0), (50, 50))
    b = c.add_rectangle((100, 0), (150, 50))
    c.set_selection({a})
    _drag(g, (125, 25), (125, 25), ctrl=True)
    assert c.state.selection == {a, b}
    _drag(g, (25, 25), (25, 25), ctrl=True)
    assert c.state.selection == {b}


def test_drag_moves_selection_in_one_undo_step():
    c, g = _setup()
    sid = c.add_rectangle((0, 0), (50, 50))
    undo_depth = len(c._undo_stack)
    g.press((25, 25), NONE)
    g.move((35, 45), NONE)
    assert g.overlay.moving == {sid} and g.overlay.matrix == affine.translation(10, 20)
    assert _shapes(c)[0].x == 0
    g.release((35, 45), NONE)
    assert (_shapes(c)[0].x, _shapes(c)[0].y) == (10, 20)
    assert len(c._undo_stack) == undo_depth + 1


def test_rubber_band_selects_intersecting_and_ctrl_adds():
    c, g = _setup()
    a = c.add_rectangle((0, 0), (50, 50))
    b = c.add_rectangle((100, 100), (150, 150))
    c.set_selection(set())
    g.press((-10, -10), NONE)
    g.move((60, 60), NONE)
    assert g.overlay.rubber_band == (-10, -10, 70, 70)
    assert g.overlay.selection == {a}
    g.release((60, 60), NONE)
    assert c.state.selection == {a}
    _drag(g, (90, 90), (120, 120), ctrl=True)
    assert c.state.selection == {a, b}


def test_pen_finishes_with_deduped_points():
    c, g = _setup()
    g.set_tool(Tool.PEN)
    for p in [(0, 0), (50, 0), (50, 1), (100, 50)]:
        g.press(p, NONE)
    g.double_click((100, 50), NONE)
    path = _shapes(c)[0]
    assert isinstance(path, PathShape)
    assert len(path.segments) == 3


def test_escape_cancels_gesture_then_clears_selection():
    c, g = _setup()
    sid = c.add_rectangle((0, 0), (50, 50))
    g.set_tool(Tool.PEN)
    g.press((0, 0), NONE)
    g.escape()
    assert g.overlay.preview is None
    assert c.state.selection == {sid}
    g.escape()
    assert c.state.selection == set()


def test_text_tool_uses_dialog_result():
    c, g = _setup(text="hello")
    g.set_tool(Tool.TEXT)
    g.press((10, 20), NONE)
    assert _shapes(c)[0].text == "hello"
    c2, g2 = _setup(text=None)
    g2.set_tool(Tool.TEXT)
    g2.press((10, 20), NONE)
    assert _shapes(c2) == []


@pytest.mark.parametrize(
    "angle, expected",
    [
        (0, CursorType.RESIZE_H),
        (180, CursorType.RESIZE_H),
        (-170, CursorType.RESIZE_H),
        (90, CursorType.RESIZE_V),
        (-90, CursorType.RESIZE_V),
        (45, CursorType.RESIZE_FDIAG),
        (-135, CursorType.RESIZE_FDIAG),
        (135, CursorType.RESIZE_BDIAG),
        (-45, CursorType.RESIZE_BDIAG),
        (60, CursorType.RESIZE_FDIAG),
        (70, CursorType.RESIZE_V),
    ],
)
def test_resize_cursor_type_picks_nearest(angle, expected):
    assert resize_cursor_type(angle) is expected


def test_hover_move_over_shape_arrow_on_empty_canvas():
    c, g = _setup()
    c.add_rectangle((0, 0), (50, 50))
    c.set_selection(set())
    assert g.hover((25, 25)) is CursorType.MOVE
    assert g.hover((200, 200)) is CursorType.ARROW


def test_hover_drawing_tools():
    c, g = _setup()
    g.set_tool(Tool.RECTANGLE)
    assert g.hover((0, 0)) is CursorType.CROSS
    g.set_tool(Tool.TEXT)
    assert g.hover((0, 0)) is CursorType.IBEAM


def test_hover_keeps_press_cursor_during_drag():
    c, g = _setup()
    c.add_rectangle((0, 0), (50, 50))
    g.press((25, 25), NONE)
    g.move((300, 300), NONE)
    assert g.hover((300, 300)) is CursorType.MOVE
    g.release((300, 300), NONE)


# --- scale / rotate handles --------------------------------------------------------


def _rect_selected(c, x0=100, y0=100, x1=200, y1=150):
    sid = c.add_rectangle((x0, y0), (x1, y1))
    return sid


def test_se_corner_doubles_size_with_nw_fixed():
    c, g = _setup()
    sid = _rect_selected(c)
    _drag(g, (200, 150), (300, 200))
    rect = c.find_shape(sid)
    assert (rect.x, rect.y, rect.width, rect.height) == pytest.approx((100, 100, 200, 100))


def test_scale_is_one_undo_step_and_previews_live():
    c, g = _setup()
    sid = _rect_selected(c)
    undo_depth = len(c._undo_stack)
    g.press((200, 150), NONE)
    g.move((300, 200), NONE)
    assert c.find_shape(sid).width == 100
    (live,) = g.overlay.live
    assert live.width == pytest.approx(200)
    assert g.overlay.frame.corners()[2] == pytest.approx((300, 200))
    g.release((300, 200), NONE)
    assert len(c._undo_stack) == undo_depth + 1


def test_edge_handle_scales_one_axis():
    c, g = _setup()
    sid = _rect_selected(c)
    _drag(g, (200, 125), (250, 180))
    rect = c.find_shape(sid)
    assert (rect.x, rect.y, rect.width, rect.height) == pytest.approx((100, 100, 150, 50))


def test_shift_corner_keeps_aspect_ratio():
    c, g = _setup()
    sid = _rect_selected(c)
    _drag(g, (200, 150), (400, 160), shift=True)
    rect = c.find_shape(sid)
    assert (rect.width, rect.height) == pytest.approx((300, 150))


def test_shift_edge_scales_uniformly():
    c, g = _setup()
    sid = _rect_selected(c)
    _drag(g, (200, 125), (300, 125), shift=True)
    rect = c.find_shape(sid)
    assert (rect.width, rect.height) == pytest.approx((200, 100))
    assert rect.y == pytest.approx(75)


def test_alt_scales_about_center():
    c, g = _setup()
    sid = _rect_selected(c)
    _drag(g, (200, 150), (250, 175), alt=True)
    rect = c.find_shape(sid)
    assert (rect.x, rect.y, rect.width, rect.height) == pytest.approx((50, 75, 200, 100))


def test_drag_past_opposite_edge_flips():
    c, g = _setup()
    sid = _rect_selected(c)
    _drag(g, (200, 125), (50, 125))
    rect = c.find_shape(sid)
    assert (rect.x, rect.width) == pytest.approx((50, 50))


def test_tiny_drag_clamps_to_one_screen_px():
    c, g = _setup()
    sid = _rect_selected(c)
    g.pixel_size = 0.5
    _drag(g, (200, 125), (100, 125))
    assert c.find_shape(sid).width == pytest.approx(0.5)


def test_rotated_rect_scales_along_own_axes():
    c, g = _setup()
    sid = _rect_selected(c)
    c.set_rotation(sid, 90)
    # Rotated 90° about (150, 125): the shape's E edge midpoint is now at the bottom (150, 175).
    _drag(g, (150, 175), (150, 225))
    rect = c.find_shape(sid)
    assert (rect.width, rect.height) == pytest.approx((150, 50))
    assert geometry.rotation_of(rect) == pytest.approx(90)


def test_rotate_zone_rotates_about_frame_center():
    c, g = _setup()
    sid = _rect_selected(c, 100, 100, 200, 200)
    # NE rotate zone at (210, 90); rotating it to (210, 210) about (150, 150) sweeps 90°.
    g.press((210, 90), NONE)
    g.move((210, 210), NONE)
    assert g.hint == "Rotate 90.0°"
    g.release((210, 210), NONE)
    assert geometry.rotation_of(c.find_shape(sid)) == pytest.approx(90)


def test_shift_rotation_snaps_to_15_degrees():
    c, g = _setup()
    sid = _rect_selected(c, 100, 100, 200, 120)
    # NE corner (200, 100), center (150, 110). Sweep about 40° snaps to 45°.
    cx, cy = 150, 110
    start = (210, 95)
    a0 = math.atan2(start[1] - cy, start[0] - cx)
    r = math.hypot(start[0] - cx, start[1] - cy)
    end = (cx + r * math.cos(a0 + math.radians(40)), cy + r * math.sin(a0 + math.radians(40)))
    _drag(g, start, end, shift=True)
    assert geometry.rotation_of(c.find_shape(sid)) == pytest.approx(45)


def test_escape_cancels_scale_without_undo_entry():
    c, g = _setup()
    sid = _rect_selected(c)
    undo_depth = len(c._undo_stack)
    g.press((200, 150), NONE)
    g.move((300, 200), NONE)
    g.escape()
    assert c.find_shape(sid).width == 100
    assert len(c._undo_stack) == undo_depth
    assert c.state.selection == {sid}


def test_hover_over_handles():
    c, g = _setup()
    _rect_selected(c)
    assert g.hover((200, 125)) is CursorType.RESIZE_H
    assert g.hover((150, 100)) is CursorType.RESIZE_V
    assert g.hover((200, 150)) is CursorType.RESIZE_FDIAG
    assert g.hover((200, 100)) is CursorType.RESIZE_BDIAG
    assert g.hover((212, 88)) is CursorType.ROTATE


def test_hover_resize_follows_rotation():
    c, g = _setup()
    sid = _rect_selected(c)
    c.set_rotation(sid, 90)
    assert g.hover((150, 175)) is CursorType.RESIZE_V


# --- node tool -----------------------------------------------------------------------


def _node_setup():
    c, g = _setup()
    sid = c.add_path([(0, 0), (100, 0), (200, 100)])
    c.select_tool(Tool.NODE)
    g.set_tool(Tool.NODE)
    return c, g, sid


def test_node_click_selects_and_shift_toggles():
    c, g, sid = _node_setup()
    _drag(g, (100, 0), (100, 0))
    assert c.state.node_selection == {(sid, 1)}
    _drag(g, (200, 100), (200, 100), shift=True)
    assert c.state.node_selection == {(sid, 1), (sid, 2)}
    _drag(g, (100, 0), (100, 0), shift=True)
    assert c.state.node_selection == {(sid, 2)}


def test_node_band_selects_nodes():
    c, g, sid = _node_setup()
    _drag(g, (-10, -10), (150, 20))
    assert c.state.node_selection == {(sid, 0), (sid, 1)}


def test_node_drag_commits_one_move():
    c, g, sid = _node_setup()
    depth = len(c._undo_stack)
    g.press((100, 0), NONE)
    g.move((110, 20), NONE)
    (live,) = g.overlay.live
    assert (live.segments[1].x, live.segments[1].y) == (110, 20)
    assert c.find_shape(sid).segments[1].x == 100
    g.release((110, 20), NONE)
    assert (c.find_shape(sid).segments[1].x, c.find_shape(sid).segments[1].y) == (110, 20)
    assert len(c._undo_stack) == depth + 1


def test_control_drag_keeps_smooth_unless_alt():
    c, g, sid = _node_setup()
    _drag(g, (100, 0), (100, 0))
    path = c.find_shape(sid)
    c2 = (path.segments[1].c2x, path.segments[1].c2y)
    _drag(g, c2, (c2[0] - 10, c2[1] - 30))
    smooth = c.find_shape(sid)
    assert smooth.segments[2] != path.segments[2]
    c.undo()
    c.set_node_selection({(sid, 1)})
    _drag(g, c2, (c2[0] - 10, c2[1] - 30), alt=True)
    assert c.find_shape(sid).segments[2] == path.segments[2]


def test_double_click_on_segment_inserts_node():
    c, g, sid = _node_setup()
    path = c.find_shape(sid)
    on_curve = nodes._eval(path.segments, nodes._Topology(path.segments), 2, 0.5)
    g.double_click(on_curve, NONE)
    assert len(c.find_shape(sid).segments) == len(path.segments) + 1
    assert c.state.node_selection == {(sid, 2)}


def test_node_escape_order():
    c, g, sid = _node_setup()
    _drag(g, (100, 0), (100, 0))
    g.press((100, 0), NONE)
    g.move((120, 0), NONE)
    g.escape()
    assert g.overlay.live == () and c.find_shape(sid).segments[1].x == 100
    assert c.state.node_selection == {(sid, 1)}
    g.escape()
    assert c.state.node_selection == frozenset() and c.state.selection == {sid}
    g.escape()
    assert c.state.selection == set()


def test_node_hover_types_and_hint_for_rect():
    c, g, sid = _node_setup()
    assert g.hover((100, 0)) is CursorType.NODE
    path = c.find_shape(sid)
    on_curve = nodes._eval(path.segments, nodes._Topology(path.segments), 2, 0.5)
    assert g.hover(on_curve) is CursorType.NODE_INSERT
    assert g.hover((500, 500)) is CursorType.ARROW
    assert g.hint is None
    rect = c.add_rectangle((300, 300), (350, 350))
    c.set_selection({rect})
    assert "Object to Path" in g.hint


def test_node_overlay_shows_controls_of_selected_nodes():
    c, g, sid = _node_setup()
    assert g.overlay.nodes[0].controls == frozenset()
    _drag(g, (100, 0), (100, 0))
    (overlay,) = g.overlay.nodes
    assert overlay.selected == {1}
    assert overlay.controls == {(1, 1), (1, 2), (2, 1), (2, 2)}
