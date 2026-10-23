import skia

from presstoshape.geometry.segments import rect_segments
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import (
    EllipseShape,
    GradientStop,
    GroupShape,
    LinearGradient,
    Masking,
    PathShape,
    RectShape,
    Style,
)
from presstoshape.render.overlay import CanvasColors, Overlay
from presstoshape.render.paths import PathCache
from presstoshape.render.scene import draw_document, draw_edit_mode

SIZE = 100
RED = "#ff0000"
CLEAR = (0, 0, 0, 0)


def _style(fill="#000000", **fields) -> Style:
    return Style(fill=fill, stroke=None, **fields)


def _rect(shape_id, x, y, w, h, fill="#000000", **fields) -> RectShape:
    return RectShape(shape_id, x, y, w, h, _style(fill, **fields))


def _group(content, mask, mask_type="clip", **fields) -> GroupShape:
    children = (*content, *mask)
    return GroupShape(1000, children, masking=Masking(mask_type, tuple(s.id for s in mask), **fields))


def _render(*shapes) -> skia.Surface:
    doc = Document(SIZE, SIZE, [Layer("L", True, list(shapes))])
    surface = skia.Surface(SIZE, SIZE)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    draw_document(surface.getCanvas(), doc, PathCache())
    return surface


def _pixel(surface, x, y):
    return tuple(int(v) for v in surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[y, x])


def _alpha(surface, x, y) -> int:
    return _pixel(surface, x, y)[3]


def _close(actual, expected, tolerance=6):
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


def test_clip_cuts_content_to_mask_object():
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 20, 20, 40, 40)]))
    assert _pixel(surface, 30, 30) == (255, 0, 0, 255)
    assert _pixel(surface, 70, 70) == CLEAR
    assert _pixel(surface, 10, 10) == CLEAR


def test_clip_ignores_fill_stroke_and_opacity_of_mask_object():
    mask = RectShape(2, 20, 20, 40, 40, Style(fill=None, stroke="#00ff00", stroke_width=20, opacity=0.1))
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [mask]))
    assert _pixel(surface, 30, 30) == (255, 0, 0, 255)
    assert _pixel(surface, 15, 30) == CLEAR


def test_clip_is_union_of_mask_objects():
    mask = [_rect(2, 0, 0, 30, 30), _rect(3, 60, 60, 30, 30)]
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], mask))
    assert _alpha(surface, 10, 10) == 255
    assert _alpha(surface, 70, 70) == 255
    assert _alpha(surface, 10, 70) == 0


def test_clip_respects_fill_rule_of_mask_object():
    segments = rect_segments(10, 10, 80, 80) + rect_segments(30, 30, 40, 40)
    even = PathShape(2, segments, _style(fill_rule="evenodd"))
    odd_hole = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [even]))
    assert _alpha(odd_hole, 50, 50) == 0
    assert _alpha(odd_hole, 15, 50) == 255
    nonzero = PathShape(2, segments, _style(fill_rule="nonzero"))
    filled = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [nonzero]))
    assert _alpha(filled, 50, 50) == 255


def test_clip_follows_transformed_mask_object():
    mask = RectShape(2, 0, 0, 20, 20, _style(), transform=(1, 0, 0, 1, 50, 50))
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [mask]))
    assert _alpha(surface, 60, 60) == 255
    assert _alpha(surface, 10, 10) == 0


def test_inverted_clip_cuts_hole():
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 20, 20, 40, 40)], inverted=True))
    assert _alpha(surface, 30, 30) == 0
    assert _alpha(surface, 80, 80) == 255


def test_clip_is_anti_aliased():
    mask = EllipseShape(2, 50, 50, 30, 30, _style())
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [mask]))
    edge = [_alpha(surface, x, 50) for x in range(18, 24)]
    assert any(0 < a < 255 for a in edge) or edge[0] == 0 and edge[-1] == 255


def test_nested_clip_intersects():
    inner = GroupShape(500, (_rect(1, 0, 0, 100, 100, RED), _rect(2, 0, 0, 50, 100)), masking=Masking("clip", (2,)))
    outer = GroupShape(1000, (inner, _rect(3, 25, 0, 50, 100)), masking=Masking("clip", (3,)))
    surface = _render(outer)
    assert _alpha(surface, 35, 50) == 255
    assert _alpha(surface, 10, 50) == 0
    assert _alpha(surface, 60, 50) == 0


def test_clip_with_nested_masked_group_as_mask_object():
    nested = GroupShape(500, (_rect(2, 0, 0, 100, 100), _rect(3, 0, 0, 50, 50)), masking=Masking("clip", (3,)))
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [nested]))
    assert _alpha(surface, 25, 25) == 255
    assert _alpha(surface, 75, 75) == 0


def test_empty_clip_hides_content_and_inverted_empty_clip_shows_it():
    content = [_rect(1, 0, 0, 100, 100, RED)]
    assert _alpha(_render(_group(content, [])), 50, 50) == 0
    assert _alpha(_render(_group(content, [], inverted=True)), 50, 50) == 255


def test_hidden_mask_object_does_not_clip():
    mask = RectShape(2, 20, 20, 40, 40, _style(), hidden=True)
    assert _alpha(_render(_group([_rect(1, 0, 0, 100, 100, RED)], [mask])), 30, 30) == 0


def test_luminance_white_shows_black_hides():
    mask = [_rect(2, 0, 0, 50, 100, "#ffffff"), _rect(3, 50, 0, 50, 100, "#000000")]
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], mask, "luminance"))
    assert _pixel(surface, 25, 50) == (255, 0, 0, 255)
    assert _alpha(surface, 75, 50) == 0


def test_luminance_outside_mask_objects_hides():
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 0, 0, 40, 100, "#ffffff")], "luminance"))
    assert _alpha(surface, 70, 50) == 0


def test_luminance_grey_and_alpha_multiply():
    grey = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 0, 0, 100, 100, "#808080")], "luminance"))
    assert abs(_alpha(grey, 50, 50) - 128) <= 4
    half = _render(
        _group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 0, 0, 100, 100, "#ffffff", opacity=0.5)], "luminance")
    )
    assert abs(_alpha(half, 50, 50) - 128) <= 4


def test_luminance_gradient_ramps_alpha():
    ramp = LinearGradient(0, 0, 1, 0, (GradientStop(0, "#000000"), GradientStop(1, "#ffffff")))
    mask = RectShape(2, 0, 0, 100, 100, Style(fill=ramp, stroke=None))
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [mask], "luminance"))
    left, middle, right = (_alpha(surface, x, 50) for x in (5, 50, 95))
    assert left < 40 < middle < 215 < right


def test_luminance_stroke_of_mask_object_counts():
    mask = RectShape(2, 20, 20, 60, 60, Style(fill=None, stroke="#ffffff", stroke_width=10))
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], [mask], "luminance"))
    assert _alpha(surface, 20, 50) == 255
    assert _alpha(surface, 50, 50) == 0


def test_luminance_inverted():
    surface = _render(
        _group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 0, 0, 50, 100, "#ffffff")], "luminance", inverted=True)
    )
    assert _alpha(surface, 25, 50) == 0
    assert _alpha(surface, 75, 50) == 255


def test_luminance_region_cuts_content():
    surface = _render(
        _group(
            [_rect(1, 0, 0, 100, 100, RED)],
            [_rect(2, 0, 0, 100, 100, "#ffffff")],
            "luminance",
            region=(20.0, 20.0, 40.0, 40.0),
        )
    )
    assert _alpha(surface, 30, 30) == 255
    assert _alpha(surface, 80, 80) == 0


def test_alpha_type_uses_mask_alpha_not_colour():
    mask = [_rect(2, 0, 0, 50, 100, "#000000")]
    surface = _render(_group([_rect(1, 0, 0, 100, 100, RED)], mask, "alpha"))
    assert _pixel(surface, 25, 50) == (255, 0, 0, 255)
    assert _alpha(surface, 75, 50) == 0


def test_alpha_inverted_and_semi_transparent():
    mask = [_rect(2, 0, 0, 50, 100, "#000000", opacity=0.5)]
    plain = _render(_group([_rect(1, 0, 0, 100, 100, RED)], mask, "alpha"))
    assert abs(_alpha(plain, 25, 50) - 128) <= 4
    inverted = _render(_group([_rect(1, 0, 0, 100, 100, RED)], mask, "alpha", inverted=True))
    assert abs(_alpha(inverted, 25, 50) - 127) <= 4
    assert _alpha(inverted, 75, 50) == 255


def test_empty_mask_hides_content():
    assert _alpha(_render(_group([_rect(1, 0, 0, 100, 100, RED)], [], "luminance")), 50, 50) == 0
    assert _alpha(_render(_group([_rect(1, 0, 0, 100, 100, RED)], [], "alpha")), 50, 50) == 0


def test_masked_group_with_opacity():
    group = _group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 0, 0, 50, 100, "#ffffff")], "luminance")
    from dataclasses import replace

    surface = _render(replace(group, opacity=0.5))
    assert abs(_alpha(surface, 25, 50) - 128) <= 4
    assert _alpha(surface, 75, 50) == 0


def test_masked_group_inside_masked_group():
    inner = GroupShape(
        500,
        (_rect(1, 0, 0, 100, 100, RED), _rect(2, 0, 0, 100, 100, "#ffffff")),
        masking=Masking("luminance", (2,)),
    )
    outer = GroupShape(1000, (inner, _rect(3, 0, 0, 50, 100)), masking=Masking("clip", (3,)))
    surface = _render(outer)
    assert _alpha(surface, 25, 50) == 255
    assert _alpha(surface, 75, 50) == 0


def test_group_without_masking_still_draws_every_child():
    surface = _render(GroupShape(9, (_rect(1, 0, 0, 50, 50, RED), _rect(2, 50, 50, 50, 50, RED))))
    assert _alpha(surface, 25, 25) == 255 and _alpha(surface, 75, 75) == 255


def test_bounds_of_clip_group_is_content_cut_by_clip():
    cache = PathCache()
    group = _group([_rect(1, 0, 0, 100, 100)], [_rect(2, 20, 20, 40, 40)])
    bounds = cache.bounds(group)
    assert (bounds.left(), bounds.top(), bounds.right(), bounds.bottom()) == (20, 20, 60, 60)
    geometry = cache.geometry_bounds(group)
    assert (geometry.left(), geometry.right()) == (20, 60)


def test_bounds_ignore_mask_objects_outside_content():
    cache = PathCache()
    group = _group([_rect(1, 0, 0, 50, 50)], [_rect(2, 0, 0, 500, 500)], "luminance")
    assert cache.bounds(group).right() == 50


def test_bounds_of_inverted_clip_is_content():
    cache = PathCache()
    group = _group([_rect(1, 0, 0, 100, 100)], [_rect(2, 20, 20, 40, 40)], inverted=True)
    assert cache.bounds(group).right() == 100


def test_bounds_with_region():
    cache = PathCache()
    group = _group([_rect(1, 0, 0, 100, 100)], [_rect(2, 0, 0, 100, 100)], "luminance", region=(10.0, 10.0, 20.0, 20.0))
    bounds = cache.bounds(group)
    assert (bounds.left(), bounds.right()) == (10, 30)


def test_bounds_of_fully_clipped_group_fall_back_to_content():
    cache = PathCache()
    group = _group([_rect(1, 0, 0, 10, 10)], [_rect(2, 50, 50, 10, 10)])
    assert cache.bounds(group).right() == 10


def test_clip_cache_identity_and_invalidation():
    cache = PathCache()
    group = _group([_rect(1, 0, 0, 100, 100)], [_rect(2, 20, 20, 40, 40)])
    first = cache.clip(group)
    assert cache.clip(group) is first
    moved = _group([_rect(1, 0, 0, 100, 100)], [_rect(2, 30, 30, 40, 40)])
    assert cache.clip(moved) is not first
    assert cache.clip(moved).computeTightBounds().left() == 30
    cache.prune([])
    assert cache.clip(group) is not first


def test_entered_masked_group_draws_content_unmasked():
    group = _group([_rect(1, 0, 0, 100, 100, RED)], [_rect(2, 20, 20, 40, 40)])
    colors = CanvasColors("#000000", "#ffffff", "#888888", "#00ff00", "#0000ff")
    surface = skia.Surface(SIZE, SIZE)
    surface.getCanvas().clear(skia.ColorTRANSPARENT)
    draw_edit_mode(surface.getCanvas(), [group], Overlay(), 1.0, colors, PathCache())
    assert _pixel(surface, 80, 80)[3] == 255
    pixel = _pixel(surface, 80, 80)
    assert pixel[0] > pixel[1]
