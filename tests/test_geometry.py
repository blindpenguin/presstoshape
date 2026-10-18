import math

import pytest

from veccy.controllers import affine, geometry
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


# --- transforms -----------------------------------------------------------------

S = Style()


def _rot(deg, cx, cy):
    return affine.rotation(math.radians(deg), cx, cy)


def test_new_shapes_have_identity_transform():
    assert RectShape(1, 0, 0, 10, 10, S).transform == affine.IDENTITY


def test_outline_applies_transform():
    rect = RectShape(1, 0, 0, 10, 10, S, _rot(90, 5, 5))
    x0, y0, x1, y1 = _bbox(geometry.outline(rect))
    assert (x0, y0, x1, y1) == pytest.approx((0, 0, 10, 10))
    first = geometry.outline(rect)[0]
    assert (first.x, first.y) == pytest.approx((10, 0))


def test_scale_rect_goes_into_size():
    rect = RectShape(1, 10, 10, 20, 10, S)
    out = geometry.transform_shape(rect, affine.scaling(2, 3, 10, 10))
    assert (out.x, out.y, out.width, out.height) == pytest.approx((10, 10, 40, 30))
    assert out.transform == affine.IDENTITY


def test_flip_rect_stays_untransformed():
    rect = RectShape(1, 0, 0, 20, 10, S)
    out = geometry.transform_shape(rect, affine.scaling(-1, 1, 0, 0))
    assert (out.x, out.y, out.width, out.height) == pytest.approx((-20, 0, 20, 10))
    assert affine.is_identity(out.transform)


def test_rotate_rect_keeps_rect_with_rotation_about_center():
    rect = RectShape(1, 0, 0, 20, 10, S)
    out = geometry.transform_shape(rect, _rot(30, 0, 0))
    assert isinstance(out, RectShape)
    assert (out.width, out.height) == pytest.approx((20, 10))
    angle, cx, cy = affine.as_rotation(out.transform)
    assert angle == pytest.approx(30)
    assert (cx, cy) == pytest.approx((out.x + 10, out.y + 5))
    assert _bbox(geometry.outline(out)) == pytest.approx(_bbox(geometry.transform_segments(
        geometry.outline(rect), lambda x, y: affine.apply(_rot(30, 0, 0), x, y))))


def test_scale_rotated_rect_along_own_axes():
    rect = geometry.with_rotation(RectShape(1, 0, 0, 20, 10, S), 90)
    # Shape's own x axis now points down in the document; stretch it there.
    out = geometry.transform_shape(rect, affine.scaling(1, 2, 10, 5))
    assert (out.width, out.height) == pytest.approx((40, 10))
    assert geometry.rotation_of(out) == pytest.approx(90)


def test_skewed_rect_keeps_full_matrix():
    rect = geometry.with_rotation(RectShape(1, 0, 0, 20, 10, S), 30)
    out = geometry.transform_shape(rect, affine.scaling(2, 1))
    assert (out.width, out.height) == (20, 10)
    assert geometry.rotation_of(out) is None


def test_min_extent_clamps_size():
    rect = RectShape(1, 0, 0, 20, 10, S)
    out = geometry.transform_shape(rect, affine.scaling(0.001, 1), min_extent=1.0)
    assert out.width == pytest.approx(1.0)


def test_singular_transform_raises():
    with pytest.raises(ValueError):
        geometry.transform_shape(RectShape(1, 0, 0, 20, 10, S), affine.scaling(0, 1))


def test_scale_ellipse_radii():
    ellipse = EllipseShape(1, 10, 10, 5, 5, S)
    out = geometry.transform_shape(ellipse, affine.scaling(2, 1, 5, 10))
    assert (out.cx, out.cy, out.rx, out.ry) == pytest.approx((15, 10, 10, 5))


def test_path_transform_is_baked():
    path = PathShape(1, (MoveTo(0, 0), LineTo(10, 0)), S)
    out = geometry.transform_shape(path, _rot(90, 0, 0))
    assert out.transform == affine.IDENTITY
    assert (out.segments[1].x, out.segments[1].y) == pytest.approx((0, 10))


def test_text_scales_uniformly_by_larger_factor():
    text = TextShape(1, 10, 20, "Hi", 10.0, S)
    out = geometry.transform_shape(text, affine.scaling(3, 1.5, 0, 0))
    assert (out.x, out.y, out.font_size) == pytest.approx((30, 30, 30))
    assert out.transform == affine.IDENTITY


def test_text_rotation_about_anchor():
    text = TextShape(1, 10, 20, "Hi", 10.0, S)
    out = geometry.transform_shape(text, _rot(45, 10, 20))
    assert (out.x, out.y) == pytest.approx((10, 20))
    assert geometry.rotation_of(out) == pytest.approx(45)


def test_text_flip_keeps_previous_rotation():
    text = geometry.with_rotation(TextShape(1, 10, 20, "Hi", 10.0, S), 20)
    out = geometry.transform_shape(text, affine.scaling(-1, 1, 10, 20))
    assert geometry.rotation_of(out) == pytest.approx(20)
    assert out.font_size == pytest.approx(10)


def test_translate_rotated_rect_keeps_rotation_about_new_center():
    rect = geometry.with_rotation(RectShape(1, 0, 0, 20, 10, S), 30)
    out = geometry.translate(rect, 5, 7)
    angle, cx, cy = affine.as_rotation(out.transform)
    assert angle == pytest.approx(30)
    assert (cx, cy) == pytest.approx((15, 12))
    before, after = geometry.outline(rect), geometry.outline(out)
    assert (after[0].x - before[0].x, after[0].y - before[0].y) == pytest.approx((5, 7))


def test_rotation_of_and_with_rotation():
    rect = RectShape(1, 0, 0, 20, 10, S)
    assert geometry.rotation_of(rect) == 0.0
    assert geometry.rotation_of(geometry.with_rotation(rect, -60)) == pytest.approx(-60)
    assert geometry.with_rotation(rect, 0).transform == affine.IDENTITY
