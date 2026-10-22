import math

import skia

from presstoshape.geometry import affine
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import (
    EllipseShape,
    GradientStop,
    LinearGradient,
    PathShape,
    RadialGradient,
    RectShape,
    Style,
    TextShape,
)
from presstoshape.render.hit_test import shape_at
from presstoshape.render.paths import PathCache
from presstoshape.render.scene import draw_document

RED_BLUE = (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff"))


def _render(*shapes, size=100) -> skia.Surface:
    doc = Document(size, size, [Layer("L", True, list(shapes))])
    surface = skia.Surface(size, size)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    draw_document(surface.getCanvas(), doc, PathCache())
    return surface


def _pixel(surface, x, y):
    return tuple(int(v) for v in surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[y, x])


def _close(actual, expected, tolerance=6):
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def _linear(stops=RED_BLUE, **changes):
    return LinearGradient(**({"x1": 0, "y1": 0, "x2": 1, "y2": 0, "stops": stops} | changes))


def _rect(paint, x=0, y=0, w=100, h=100, **style):
    return RectShape(1, x, y, w, h, Style(fill=paint, stroke=None, **style))


def test_linear_gradient_runs_across_the_bounding_box():
    surface = _render(_rect(_linear()))
    assert _close(_pixel(surface, 1, 50), (255, 0, 0, 255), 8)
    assert _close(_pixel(surface, 50, 50), (128, 0, 128, 255), 8)
    assert _close(_pixel(surface, 98, 50), (0, 0, 255, 255), 8)


def test_bounding_box_follows_a_non_square_shape_offset_from_the_origin():
    surface = _render(_rect(_linear(), x=20, y=10, w=60, h=20))
    assert _close(_pixel(surface, 21, 20), (255, 0, 0, 255), 8)
    assert _close(_pixel(surface, 78, 20), (0, 0, 255, 255), 8)
    assert _close(_pixel(surface, 50, 20), (128, 0, 128, 255), 8)


def test_vertical_bounding_box_gradient_is_stretched_to_the_box():
    surface = _render(_rect(_linear(x2=0, y2=1), w=100, h=40))
    assert _close(_pixel(surface, 50, 1), (255, 0, 0, 255), 12)
    assert _close(_pixel(surface, 50, 38), (0, 0, 255, 255), 12)


def test_pad_extends_the_end_colours():
    surface = _render(_rect(_linear(units="userSpaceOnUse", x1=40, x2=60)))
    assert _close(_pixel(surface, 5, 50), (255, 0, 0, 255))
    assert _close(_pixel(surface, 95, 50), (0, 0, 255, 255))


def test_repeat_and_reflect():
    repeat = _render(_rect(_linear(units="userSpaceOnUse", x1=0, x2=50, spread="repeat")))
    assert _close(_pixel(repeat, 51, 50), (255, 0, 0, 255), 12)
    assert _close(_pixel(repeat, 98, 50), (0, 0, 255, 255), 12)
    reflect = _render(_rect(_linear(units="userSpaceOnUse", x1=0, x2=50, spread="reflect")))
    assert _close(_pixel(reflect, 98, 50), (255, 0, 0, 255), 12)
    assert _close(_pixel(reflect, 51, 50), (0, 0, 255, 255), 12)


def test_gradient_transform_applies():
    scaled = _linear(units="userSpaceOnUse", x2=100, transform=(0.5, 0, 0, 1, 0, 0))
    surface = _render(_rect(scaled))
    assert _close(_pixel(surface, 49, 50), (0, 0, 255, 255), 12)
    assert _close(_pixel(surface, 25, 50), (128, 0, 128, 255), 12)


def test_user_space_gradient_follows_the_shape_transform():
    moved = RectShape(
        1, 0, 0, 50, 50, Style(fill=_linear(units="userSpaceOnUse", x2=50), stroke=None), transform=(1, 0, 0, 1, 40, 40)
    )
    surface = _render(moved)
    assert _close(_pixel(surface, 41, 60), (255, 0, 0, 255), 12)
    assert _close(_pixel(surface, 88, 60), (0, 0, 255, 255), 12)


def test_radial_gradient():
    paint = RadialGradient(0.5, 0.5, 0.5, 0.5, 0.5, (GradientStop(0, "#ffffff"), GradientStop(1, "#000000")))
    surface = _render(EllipseShape(1, 50, 50, 50, 50, Style(fill=paint, stroke=None)))
    assert _close(_pixel(surface, 50, 50), (255, 255, 255, 255), 10)
    assert _close(_pixel(surface, 50, 95), (13, 13, 13, 255), 30)
    assert _pixel(surface, 2, 2)[3] == 0


def test_focal_point_moves_the_bright_spot():
    paint = RadialGradient(0.5, 0.5, 0.5, 0.2, 0.5, (GradientStop(0, "#ffffff"), GradientStop(1, "#000000")))
    surface = _render(_rect(paint))
    left, right = _pixel(surface, 25, 50)[0], _pixel(surface, 75, 50)[0]
    assert left > right + 50


def test_stop_opacity_and_fill_opacity_multiply():
    paint = _linear((GradientStop(0, "#ff0000", 0.5), GradientStop(1, "#ff0000", 0.5)))
    assert abs(_pixel(_render(_rect(paint)), 50, 50)[3] - 128) <= 2
    assert abs(_pixel(_render(_rect(paint, fill_opacity=0.5)), 50, 50)[3] - 64) <= 2


def test_stroke_gradient_uses_the_geometry_box():
    shape = RectShape(1, 20, 20, 60, 60, Style(fill=None, stroke=_linear(), stroke_width=10))
    surface = _render(shape)
    assert _close(_pixel(surface, 17, 50), (255, 0, 0, 255), 25)
    assert _close(_pixel(surface, 82, 50), (0, 0, 255, 255), 25)


def test_zero_size_box_draws_nothing():
    flat = PathShape(1, rect_segments(10, 50, 80, 0, 0, 0)[:2], Style(fill=_linear(), stroke=None))
    assert _pixel(_render(flat), 50, 50)[3] == 0


def test_single_axis_degenerate_box_draws_nothing_for_rect():
    assert _pixel(_render(_rect(_linear(), w=50, h=0)), 25, 0)[3] == 0


def test_gradient_text_draws():
    text = TextShape(1, 10, 60, "MMMM", 60, Style(fill=_linear(), stroke=None))
    surface = _render(text)
    alpha = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[:, :, 3]
    assert alpha.sum() > 0


def test_shader_cache_reuses_and_invalidates():
    cache = PathCache()
    shape = _rect(_linear())
    first = cache.shaders(shape)
    assert cache.shaders(shape) is first
    assert first[0] is not None and first[1] is None
    changed = _rect(_linear(spread="repeat"))
    assert cache.shaders(changed) is not first
    flat = RectShape(1, 0, 0, 10, 10, Style())
    assert cache.shaders(flat) == (None, None)
    cache.prune([])
    assert cache.shaders(shape) is not first


def test_gradient_shapes_are_pickable():
    shape = _rect(_linear())
    assert shape_at([shape], PathCache(), (50.0, 50.0), 1.0) == shape.id


def test_pixels_match_for_rotated_shape_in_local_box():
    rotated = RectShape(
        1,
        0,
        0,
        60,
        20,
        Style(fill=_linear(), stroke=None),
        transform=(math.cos(0.5), math.sin(0.5), -math.sin(0.5), math.cos(0.5), 30, 20),
    )
    surface = _render(rotated)
    start = affine.apply(rotated.transform, 3, 10)
    end = affine.apply(rotated.transform, 57, 10)
    assert _close(_pixel(surface, round(start[0]), round(start[1])), (255, 0, 0, 255), 25)
    assert _close(_pixel(surface, round(end[0]), round(end[1])), (0, 0, 255, 255), 25)
