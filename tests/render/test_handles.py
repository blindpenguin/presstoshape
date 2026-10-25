import pytest

from presstoshape.geometry import transforms
from presstoshape.models.shapes import (
    CompositeShape,
    GroupShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)
from presstoshape.render.handles import (
    HANDLE_PX,
    Frame,
    Handle,
    handle_at,
    handle_direction,
    handle_points,
    node_at,
    selection_frame,
)
from presstoshape.render.paths import PathCache

S = Style()


def test_no_selection_no_frame():
    assert selection_frame([], PathCache()) is None


def test_single_unrotated_rect_frame():
    frame = selection_frame([RectShape(1, 10, 20, 30, 40, S)], PathCache())
    assert frame.rect == (10, 20, 30, 40)
    assert frame.corners() == [(10, 20), (40, 20), (40, 60), (10, 60)]


def test_single_rotated_rect_frame_follows_shape():
    rect = transforms.with_rotation(RectShape(1, 0, 0, 20, 10, S), 90)
    frame = selection_frame([rect], PathCache())
    assert frame.rect == (0, 0, 20, 10)
    assert frame.point(0, 0) == pytest.approx((15, -5))


def test_single_text_frame_uses_glyph_bounds():
    frame = selection_frame([TextShape(1, 10, 50, "Hi", 20.0, S)], PathCache())
    x, y, w, h = frame.rect
    assert x >= 10 and y + h <= 51 and w > 0 and h > 0


def test_multi_selection_frame_is_axis_aligned_union():
    rotated = transforms.with_rotation(RectShape(1, 0, 0, 20, 10, S), 90)
    path = PathShape(2, (MoveTo(50, 50), LineTo(60, 70)), S)
    frame = selection_frame([rotated, path], PathCache())
    assert frame.transform == (1, 0, 0, 1, 0, 0)
    assert frame.rect == pytest.approx((5, -5, 55, 75))


@pytest.mark.parametrize("zoom", [0.5, 1.0, 4.0])
def test_handle_at_each_handle(zoom):
    frame = Frame((0, 0, 400, 200))
    for handle, p in handle_points(frame, zoom).items():
        nudge = 3 / zoom
        assert handle_at(frame, (p[0] + nudge, p[1] - nudge), zoom) is handle
    assert len(handle_points(frame, zoom)) == 8


def test_interior_is_not_a_handle():
    assert handle_at(Frame((0, 0, 100, 100)), (50, 50), 1.0) is None


def test_rotation_zone_outside_corners_only():
    frame = Frame((0, 0, 100, 100))
    assert handle_at(frame, (112, -12), 1.0) is Handle.ROTATE_NE
    assert handle_at(frame, (-10, 110), 1.0) is Handle.ROTATE_SW
    assert handle_at(frame, (150, -50), 1.0) is None
    assert handle_at(frame, (85, 15), 1.0) is None


def test_rotation_zone_scales_with_zoom():
    frame = Frame((0, 0, 100, 100))
    assert handle_at(frame, (103, -3), 4.0) is Handle.ROTATE_NE
    assert handle_at(frame, (112, -12), 4.0) is None


def test_small_frame_hides_edge_handles():
    frame = Frame((0, 0, 10, 100))
    shown = handle_points(frame, 1.0)
    assert Handle.N not in shown and Handle.S not in shown
    assert Handle.E in shown and Handle.NE in shown
    assert 10 < 3 * HANDLE_PX


def test_handle_direction_rotates_with_frame():
    frame = Frame((0, 0, 100, 10))
    assert handle_direction(frame, Handle.E) == pytest.approx(0)
    assert handle_direction(frame, Handle.S) == pytest.approx(90)
    assert handle_direction(frame, Handle.SE) == pytest.approx(45)
    rotated = selection_frame([transforms.with_rotation(RectShape(1, 0, 0, 100, 10, S), 90)], PathCache())
    assert handle_direction(rotated, Handle.E) == pytest.approx(90)


def test_opposite_handles():
    assert Handle.NE.opposite is Handle.SW
    assert Handle.N.opposite is Handle.S
    assert Handle.W.opposite is Handle.E


def test_node_at_picks_the_nearest_and_respects_zoom():
    from presstoshape.models.shapes import CubicTo

    segments = (MoveTo(0, 0), CubicTo(4, 0, 50, 0, 60, 0))
    assert node_at(segments, (1, 0), 1.0) == ("node", 0)
    assert node_at(segments, (1, 0), 1.0, {(1, 1)}) == ("node", 0)
    assert node_at(segments, (3, 0), 1.0, {(1, 1)}) == ("control", (1, 1))
    assert node_at(segments, (1, 0), 1.0, {(1, 1)}, prefer_controls=True) == ("control", (1, 1))
    assert node_at(segments, (5, 0), 1.0) == ("node", 0)
    assert node_at(segments, (5, 0), 4.0) is None


def test_node_at_prefers_the_node_under_a_retracted_handle():
    from presstoshape.models.shapes import CubicTo

    segments = (MoveTo(0, 0), CubicTo(0, 0, 50, 0, 60, 0))
    assert node_at(segments, (0, 0), 1.0, {(1, 1)}) == ("node", 0)
    assert node_at(segments, (0, 0), 1.0, {(1, 1)}, prefer_controls=True) == ("control", (1, 1))
    assert node_at(segments, (30, 0), 1.0) is None


def test_single_composite_frame_is_axis_aligned_result_bounds():
    inner = transforms.with_rotation(RectShape(1, 0, 0, 20, 10, S), 90)
    composite = CompositeShape(10, (inner, RectShape(2, 100, 100, 5, 5, S)), ("add", "add"), S)
    frame = selection_frame([composite], PathCache())
    assert frame.transform == (1, 0, 0, 1, 0, 0)
    assert frame.rect == pytest.approx((5, -5, 100, 110))


def test_a_group_gets_an_axis_aligned_frame():
    group = GroupShape(1, (RectShape(2, 0, 0, 10, 10, Style()), RectShape(3, 20, 30, 10, 10, Style())))
    frame = selection_frame([group], PathCache())
    assert frame.rect == (0, 0, 30, 40)
