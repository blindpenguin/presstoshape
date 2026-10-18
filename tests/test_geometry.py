import pytest

from veccy.controllers import geometry
from veccy.models.shapes import Close, CubicTo, EllipseShape, LineTo, MoveTo, PathShape, RectShape, Style, TextShape


def _points(segments):
    for s in segments:
        match s:
            case MoveTo(x, y) | LineTo(x, y) | CubicTo(x=x, y=y):
                yield x, y


def _bbox(segments):
    pts = list(_points(segments))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def test_box_from_drag_normalizes_any_direction():
    assert geometry.box_from_drag((10, 10), (0, 4)) == (0, 4, 10, 6)


def test_box_from_drag_square_keeps_drag_direction():
    assert geometry.box_from_drag((10, 10), (0, 4), square=True) == (0, 0, 10, 10)


def test_smooth_segments_passes_through_points():
    pts = [(0, 0), (10, 5), (20, 0)]
    segments = geometry.smooth_segments(pts)
    assert segments[0] == MoveTo(0, 0)
    assert [(s.x, s.y) for s in segments[1:]] == pts[1:]


def test_translate_each_shape_kind():
    style = Style()
    assert geometry.translate(RectShape(1, 0, 0, 5, 5, style), 2, 3).x == 2
    assert geometry.translate(EllipseShape(1, 0, 0, 5, 5, style), 2, 3).cy == 3
    assert geometry.translate(TextShape(1, 0, 0, "a", 10, style), 2, 3).y == 3
    moved = geometry.translate(PathShape(1, (MoveTo(0, 0), LineTo(1, 1), Close()), style), 2, 3)
    assert moved.segments == (MoveTo(2, 3), LineTo(3, 4), Close())


def test_outline_none_for_text():
    assert geometry.outline(TextShape(1, 0, 0, "a", 10, Style())) is None


def test_union_of_overlapping_squares_covers_both():
    a = geometry.rect_segments(0, 0, 10, 10)
    b = geometry.rect_segments(5, 5, 10, 10)
    result = geometry.boolean([a, b], "union")
    assert sum(isinstance(s, MoveTo) for s in result) == 1
    assert _bbox(result) == (0, 0, 15, 15)


def test_difference_cuts_top_out_of_bottom():
    a = geometry.rect_segments(0, 0, 10, 10)
    b = geometry.rect_segments(5, -5, 10, 20)
    assert _bbox(geometry.boolean([a, b], "difference")) == (0, 0, 5, 10)


def test_difference_of_fully_covered_shape_is_empty():
    a = geometry.rect_segments(2, 2, 2, 2)
    b = geometry.rect_segments(0, 0, 10, 10)
    assert geometry.boolean([a, b], "difference") == ()


def test_union_with_ellipse_keeps_curves():
    a = geometry.ellipse_segments(0, 0, 10, 10)
    b = geometry.rect_segments(0, -5, 20, 10)
    result = geometry.boolean([a, b], "union")
    assert any(isinstance(s, CubicTo) for s in result)
    assert _bbox(result) == pytest.approx((-10, -10, 20, 10), abs=0.01)
