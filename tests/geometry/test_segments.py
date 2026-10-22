import pytest

from presstoshape.geometry.boxes import box_from_drag
from presstoshape.geometry.segments import rect_segments, smooth_segments
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo
from tests.helpers import bbox


def test_box_from_drag_normalizes_any_direction():
    assert box_from_drag((10, 10), (0, 4)) == (0, 4, 10, 6)


def test_box_from_drag_square_keeps_drag_direction():
    assert box_from_drag((10, 10), (0, 4), square=True) == (0, 0, 10, 10)


def test_smooth_segments_passes_through_points():
    pts = [(0, 0), (10, 5), (20, 0)]
    segments = smooth_segments(pts)
    assert segments[0] == MoveTo(0, 0)
    assert [(s.x, s.y) for s in segments[1:]] == pts[1:]


def test_rect_segments_without_radii_are_four_lines():
    assert rect_segments(1, 2, 10, 20) == (
        MoveTo(1, 2),
        LineTo(11, 2),
        LineTo(11, 22),
        LineTo(1, 22),
        Close(),
    )


def test_rounded_rect_segments_round_every_corner():
    segments = rect_segments(0, 0, 10, 20, 2, 3)
    assert sum(isinstance(s, CubicTo) for s in segments) == 4
    assert segments[0] == MoveTo(2, 0)
    assert bbox(segments) == pytest.approx((0, 0, 10, 20))


def test_rect_radii_are_clamped_to_half_the_size():
    assert rect_segments(0, 0, 10, 4, 100, 100) == rect_segments(0, 0, 10, 4, 5, 2)


def test_rect_with_one_zero_radius_is_sharp():
    assert rect_segments(0, 0, 10, 10, 3, 0) == rect_segments(0, 0, 10, 10)
