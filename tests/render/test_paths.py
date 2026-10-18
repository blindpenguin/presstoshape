from dataclasses import replace

import pytest
import skia

from veccy.geometry import transforms
from veccy.models.shapes import Close, CubicTo, EllipseShape, LineTo, MoveTo, PathShape, RectShape, Style, TextShape
from veccy.render.paths import PathCache, from_skia_path, to_skia_path

_STYLE = Style(fill="#ff0000", stroke=None)


def test_cache_returns_same_path_for_unchanged_shape():
    cache = PathCache()
    rect = RectShape(1, 0, 0, 10, 10, _STYLE)
    assert cache.get(rect) is cache.get(replace(rect))


def test_cache_rebuilds_when_shape_changes():
    cache = PathCache()
    rect = RectShape(1, 0, 0, 10, 10, _STYLE)
    first = cache.get(rect)
    moved = cache.get(replace(rect, x=5))
    assert moved is not first
    assert moved.computeTightBounds().left() == pytest.approx(5)


def test_prune_drops_dead_ids():
    cache = PathCache()
    a, b = RectShape(1, 0, 0, 1, 1, _STYLE), RectShape(2, 0, 0, 1, 1, _STYLE)
    path_a = cache.get(a)
    path_b = cache.get(b)
    cache.prune({1})
    assert cache.get(a) is path_a
    assert cache.get(b) is not path_b


def test_path_segments_convert():
    path = to_skia_path((MoveTo(0, 0), LineTo(10, 0), LineTo(10, 5), Close()))
    rect = path.computeTightBounds()
    assert (rect.width(), rect.height()) == (10, 5)


def test_ellipse_bounds():
    cache = PathCache()
    rect = cache.bounds(EllipseShape(1, 50, 50, 20, 10, _STYLE))
    assert (rect.left(), rect.top(), rect.right(), rect.bottom()) == pytest.approx((30, 40, 70, 60), abs=1e-3)


def test_bounds_include_half_stroke():
    cache = PathCache()
    shape = RectShape(1, 0, 0, 10, 10, Style(fill=None, stroke="#000", stroke_width=4))
    rect = cache.bounds(shape)
    assert (rect.left(), rect.right()) == pytest.approx((-2, 12))


def test_text_path_scales_with_font_size():
    cache = PathCache()
    small = cache.bounds(TextShape(1, 10, 50, "vecc", 10, _STYLE))
    big = cache.bounds(TextShape(2, 10, 50, "vecc", 40, _STYLE))
    assert not small.isEmpty()
    assert big.width() == pytest.approx(small.width() * 4, rel=0.02)
    assert big.bottom() <= 50 + 1


def test_empty_text_has_empty_path():
    assert PathCache().get(TextShape(1, 0, 0, "", 12, _STYLE)).isEmpty()


def test_stroke_path_respects_min_width():
    cache = PathCache()
    line = PathShape(1, (MoveTo(0, 0), LineTo(100, 0)), Style(fill=None, stroke="#000", stroke_width=1))
    thin = cache.stroke_path(line).computeTightBounds()
    wide = cache.stroke_path(line, min_width=6).computeTightBounds()
    assert thin.height() == pytest.approx(1)
    assert wide.height() == pytest.approx(6)


def test_rotated_rect_path_and_bounds_are_world_space():
    rect = transforms.with_rotation(RectShape(1, 0, 0, 20, 10, _STYLE), 90)
    b = PathCache().geometry_bounds(rect)
    assert (b.left(), b.top(), b.right(), b.bottom()) == pytest.approx((5, -5, 15, 15))


def test_rotated_text_path_is_transformed():
    text = TextShape(1, 10, 50, "Hello", 20.0, _STYLE)
    upright = PathCache().geometry_bounds(text)
    turned = PathCache().geometry_bounds(transforms.with_rotation(text, 90))
    assert turned.width() == pytest.approx(upright.height(), abs=1e-3)
    assert turned.height() == pytest.approx(upright.width(), abs=1e-3)


def test_from_skia_path_round_trip():
    segments = (MoveTo(0, 0), LineTo(10, 0), CubicTo(10, 5, 5, 10, 0, 10), Close())
    assert from_skia_path(to_skia_path(segments)) == segments


def test_from_skia_path_converts_quads_and_conics():
    path = skia.Path()
    path.moveTo(0, 0)
    path.quadTo(5, 5, 10, 0)
    path.conicTo(10, 10, 0, 10, 0.7)
    segments = from_skia_path(path)
    assert isinstance(segments[0], MoveTo)
    assert all(isinstance(s, CubicTo) for s in segments[1:])
    assert (segments[-1].x, segments[-1].y) == pytest.approx((0, 10))
