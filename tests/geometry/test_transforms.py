import math

import pytest

from presstoshape.geometry import affine, booleans, transforms
from presstoshape.geometry.segments import rect_segments, transform_segments
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)
from tests.helpers import bbox

S = Style()


def _rot(deg, cx, cy):
    return affine.rotation(math.radians(deg), cx, cy)



def test_translate_each_shape_type():
    style = Style()
    assert transforms.translate(RectShape(1, 0, 0, 5, 5, style), 2, 3).x == 2
    assert transforms.translate(EllipseShape(1, 0, 0, 5, 5, style), 2, 3).cy == 3
    assert transforms.translate(TextShape(1, 0, 0, "a", 10, style), 2, 3).y == 3
    moved = transforms.translate(PathShape(1, (MoveTo(0, 0), LineTo(1, 1), Close()), style), 2, 3)
    assert moved.segments == (MoveTo(2, 3), LineTo(3, 4), Close())



def test_outline_none_for_text():
    assert transforms.outline(TextShape(1, 0, 0, "a", 10, Style())) is None



def test_new_shapes_have_identity_transform():
    assert RectShape(1, 0, 0, 10, 10, S).transform == affine.IDENTITY



def test_outline_applies_transform():
    rect = RectShape(1, 0, 0, 10, 10, S, _rot(90, 5, 5))
    x0, y0, x1, y1 = bbox(transforms.outline(rect))
    assert (x0, y0, x1, y1) == pytest.approx((0, 0, 10, 10))
    first = transforms.outline(rect)[0]
    assert (first.x, first.y) == pytest.approx((10, 0))



def test_scale_rect_goes_into_size():
    rect = RectShape(1, 10, 10, 20, 10, S)
    out = transforms.transform_shape(rect, affine.scaling(2, 3, 10, 10))
    assert (out.x, out.y, out.width, out.height) == pytest.approx((10, 10, 40, 30))
    assert out.transform == affine.IDENTITY



def test_flip_rect_stays_untransformed():
    rect = RectShape(1, 0, 0, 20, 10, S)
    out = transforms.transform_shape(rect, affine.scaling(-1, 1, 0, 0))
    assert (out.x, out.y, out.width, out.height) == pytest.approx((-20, 0, 20, 10))
    assert affine.is_identity(out.transform)



def test_rotate_rect_keeps_rect_with_rotation_about_center():
    rect = RectShape(1, 0, 0, 20, 10, S)
    out = transforms.transform_shape(rect, _rot(30, 0, 0))
    assert isinstance(out, RectShape)
    assert (out.width, out.height) == pytest.approx((20, 10))
    angle, cx, cy = affine.as_rotation(out.transform)
    assert angle == pytest.approx(30)
    assert (cx, cy) == pytest.approx((out.x + 10, out.y + 5))
    assert bbox(transforms.outline(out)) == pytest.approx(bbox(transform_segments(
        transforms.outline(rect), lambda x, y: affine.apply(_rot(30, 0, 0), x, y))))



def test_scale_rotated_rect_along_own_axes():
    rect = transforms.with_rotation(RectShape(1, 0, 0, 20, 10, S), 90)
    # Shape's own x axis now points down in the document; stretch it there.
    out = transforms.transform_shape(rect, affine.scaling(1, 2, 10, 5))
    assert (out.width, out.height) == pytest.approx((40, 10))
    assert transforms.rotation_of(out) == pytest.approx(90)



def test_skewed_rect_keeps_full_matrix():
    rect = transforms.with_rotation(RectShape(1, 0, 0, 20, 10, S), 30)
    out = transforms.transform_shape(rect, affine.scaling(2, 1))
    assert (out.width, out.height) == (20, 10)
    assert transforms.rotation_of(out) is None



def test_min_extent_clamps_size():
    rect = RectShape(1, 0, 0, 20, 10, S)
    out = transforms.transform_shape(rect, affine.scaling(0.001, 1), min_extent=1.0)
    assert out.width == pytest.approx(1.0)



def test_singular_transform_raises():
    with pytest.raises(ValueError):
        transforms.transform_shape(RectShape(1, 0, 0, 20, 10, S), affine.scaling(0, 1))



def test_scale_ellipse_radii():
    ellipse = EllipseShape(1, 10, 10, 5, 5, S)
    out = transforms.transform_shape(ellipse, affine.scaling(2, 1, 5, 10))
    assert (out.cx, out.cy, out.rx, out.ry) == pytest.approx((15, 10, 10, 5))



def test_path_transform_is_baked():
    path = PathShape(1, (MoveTo(0, 0), LineTo(10, 0)), S)
    out = transforms.transform_shape(path, _rot(90, 0, 0))
    assert out.transform == affine.IDENTITY
    assert (out.segments[1].x, out.segments[1].y) == pytest.approx((0, 10))



def test_text_scales_uniformly_by_larger_factor():
    text = TextShape(1, 10, 20, "Hi", 10.0, S)
    out = transforms.transform_shape(text, affine.scaling(3, 1.5, 0, 0))
    assert (out.x, out.y, out.font_size) == pytest.approx((30, 30, 30))
    assert out.transform == affine.IDENTITY



def test_text_rotation_about_anchor():
    text = TextShape(1, 10, 20, "Hi", 10.0, S)
    out = transforms.transform_shape(text, _rot(45, 10, 20))
    assert (out.x, out.y) == pytest.approx((10, 20))
    assert transforms.rotation_of(out) == pytest.approx(45)



def test_text_flip_keeps_previous_rotation():
    text = transforms.with_rotation(TextShape(1, 10, 20, "Hi", 10.0, S), 20)
    out = transforms.transform_shape(text, affine.scaling(-1, 1, 10, 20))
    assert transforms.rotation_of(out) == pytest.approx(20)
    assert out.font_size == pytest.approx(10)



def test_translate_rotated_rect_keeps_rotation_about_new_center():
    rect = transforms.with_rotation(RectShape(1, 0, 0, 20, 10, S), 30)
    out = transforms.translate(rect, 5, 7)
    angle, cx, cy = affine.as_rotation(out.transform)
    assert angle == pytest.approx(30)
    assert (cx, cy) == pytest.approx((15, 12))
    before, after = transforms.outline(rect), transforms.outline(out)
    assert (after[0].x - before[0].x, after[0].y - before[0].y) == pytest.approx((5, 7))



def test_rotation_of_and_with_rotation():
    rect = RectShape(1, 0, 0, 20, 10, S)
    assert transforms.rotation_of(rect) == 0.0
    assert transforms.rotation_of(transforms.with_rotation(rect, -60)) == pytest.approx(-60)
    assert transforms.with_rotation(rect, 0).transform == affine.IDENTITY


# --- composites ---------------------------------------------------------------------------


def _composite(*parts, modes=None, shape_id=100):
    modes = modes or ("add",) * len(parts)
    return CompositeShape(shape_id, tuple(parts), tuple(modes), S)


def _area(segments) -> float:
    return booleans._to_skia(segments).area


@pytest.mark.parametrize("mode, area", [("add", 175), ("subtract", 75), ("intersect", 25), ("exclude", 150)])
def test_composite_outline_per_mode(mode, area):
    composite = _composite(RectShape(1, 0, 0, 10, 10, S), RectShape(2, 5, 5, 10, 10, S), modes=("add", mode))
    assert _area(transforms.outline(composite)) == pytest.approx(area)


def test_nested_composite_outline_uses_inner_result():
    inner = _composite(RectShape(1, 0, 0, 10, 10, S), RectShape(2, 5, 0, 5, 10, S), modes=("add", "subtract"))
    outer = _composite(inner, RectShape(3, 0, 0, 2, 10, S), modes=("add", "subtract"), shape_id=101)
    # Inner leaves x 0..5; the outer cuts x 0..2 away.
    assert bbox(transforms.outline(outer)) == pytest.approx((2, 0, 5, 10))


def test_empty_composite_result():
    composite = _composite(RectShape(1, 0, 0, 10, 10, S), RectShape(2, 0, 0, 10, 10, S), modes=("add", "subtract"))
    assert transforms.outline(composite) == ()


def test_pathops_error_gives_empty_outline(monkeypatch):
    def fail(parts):
        raise booleans.pathops.PathOpsError("degenerate")

    monkeypatch.setattr(booleans, "combine_parts", fail)
    composite = _composite(RectShape(1, 0, 0, 10, 10, S), RectShape(2, 5, 5, 10, 10, S))
    assert transforms.outline(composite) == ()


def test_translate_and_transform_composite_map_over_parts():
    inner = _composite(RectShape(1, 0, 0, 10, 10, S), EllipseShape(2, 5, 5, 3, 3, S), shape_id=101)
    outer = _composite(inner, RectShape(3, 20, 0, 5, 5, S))
    moved = transforms.translate(outer, 10, 20)
    assert moved.parts[0].parts[0].x == 10 and moved.parts[0].parts[1].cy == 25 and moved.parts[1].y == 20
    scaled = transforms.transform_shape(outer, affine.scaling(2, 2))
    assert scaled.parts[0].parts[0].width == 20 and scaled.parts[1].x == 40
    assert scaled.transform == affine.IDENTITY and transforms.rotation_of(scaled) == 0


def test_resizing_a_rounded_rect_keeps_its_radii():
    rect = RectShape(1, 0, 0, 10, 10, S, rx=2, ry=3)
    scaled = transforms.transform_shape(rect, affine.scaling(2, 3))
    assert (scaled.width, scaled.height, scaled.rx, scaled.ry) == pytest.approx((20, 30, 2, 3))


def test_scale_radii_scales_them_with_the_axes():
    rect = RectShape(1, 0, 0, 10, 10, S, rx=2, ry=3)
    scaled = transforms.transform_shape(rect, affine.scaling(2, 3), scale_radii=True)
    assert (scaled.rx, scaled.ry) == pytest.approx((4, 9))


def test_skewed_rounded_rect_keeps_radii_in_its_matrix():
    rect = RectShape(1, 0, 0, 10, 10, S, rx=2, ry=2)
    skew = (1.0, 0.0, 0.5, 1.0, 0.0, 0.0)
    skewed = transforms.transform_shape(rect, skew, scale_radii=True)
    assert (skewed.rx, skewed.ry, skewed.transform) == (2, 2, skew)


def test_rounded_rect_outline_has_round_corners():
    segments = transforms.outline(RectShape(1, 0, 0, 10, 10, S, rx=2, ry=2))
    assert sum(isinstance(s, CubicTo) for s in segments) == 4


def _ring(fill_rule):
    # Two squares wound the same way: the inner one is a hole only under evenodd.
    segments = rect_segments(0, 0, 10, 10) + rect_segments(3, 3, 4, 4)
    return PathShape(1, segments, Style(fill_rule=fill_rule))


def test_area_outline_of_an_evenodd_ring_keeps_the_hole():
    assert booleans.area(transforms.area_outline(_ring("evenodd"))) == pytest.approx(100 - 16)


def test_area_outline_leaves_nonzero_shapes_alone():
    shape = _ring("nonzero")
    assert transforms.area_outline(shape) == transforms.outline(shape)


def test_area_outline_of_text_is_none():
    assert transforms.area_outline(TextShape(1, 0, 0, "a", 12, Style(fill_rule="evenodd"))) is None


def test_composite_uses_the_area_of_evenodd_parts():
    square = RectShape(2, 20, 0, 10, 10, S)
    composite = CompositeShape(3, (_ring("evenodd"), square), ("add", "add"), S)
    assert booleans.area(transforms.outline(composite)) == pytest.approx(84 + 100)
