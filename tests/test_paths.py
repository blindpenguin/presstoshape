from dataclasses import replace

import pytest

from veccy.models.shapes import Close, EllipseShape, LineTo, MoveTo, PathShape, RectShape, Style, TextShape
from veccy.render.paths import PathCache, to_skia_path

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
