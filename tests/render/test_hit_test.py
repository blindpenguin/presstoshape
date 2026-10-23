import time

from presstoshape.geometry import transforms
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import (
    CompositeShape,
    EllipseShape,
    GroupShape,
    LineTo,
    Masking,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)
from presstoshape.render.hit_test import shape_at, shapes_in_rect
from presstoshape.render.paths import PathCache
from presstoshape.render.scene import visible_shapes

FILLED = Style(fill="#ff0000", stroke=None)
OUTLINED = Style(fill=None, stroke="#000000", stroke_width=2)


def _pickable(doc: Document) -> list:
    return list(visible_shapes(doc))


def _doc(*layers: list) -> Document:
    return Document(500, 500, [Layer(f"L{i}", True, list(shapes)) for i, shapes in enumerate(layers)])


def test_top_most_shape_wins():
    doc = _doc([RectShape(1, 0, 0, 100, 100, FILLED)], [RectShape(2, 50, 50, 100, 100, FILLED)])
    assert shape_at(_pickable(doc), PathCache(), (75, 75), 0) == 2
    assert shape_at(_pickable(doc), PathCache(), (25, 25), 0) == 1


def test_miss_returns_none():
    doc = _doc([RectShape(1, 0, 0, 10, 10, FILLED)])
    assert shape_at(_pickable(doc), PathCache(), (50, 50), 3) is None


def test_unfilled_shape_is_hit_only_near_stroke():
    doc = _doc([RectShape(1, 0, 0, 100, 100, OUTLINED)])
    cache = PathCache()
    assert shape_at(_pickable(doc), cache, (50, 50), 3) is None
    assert shape_at(_pickable(doc), cache, (0, 50), 3) == 1
    assert shape_at(_pickable(doc), cache, (2.5, 50), 3) == 1
    assert shape_at(_pickable(doc), cache, (6, 50), 3) is None


def test_click_through_unfilled_shape_hits_shape_below():
    doc = _doc([RectShape(1, 0, 0, 100, 100, FILLED)], [RectShape(2, 10, 10, 80, 80, OUTLINED)])
    assert shape_at(_pickable(doc), PathCache(), (50, 50), 3) == 1


def test_hidden_layer_is_ignored():
    doc = _doc([RectShape(1, 0, 0, 100, 100, FILLED)])
    doc.layers[0].visible = False
    assert shape_at(_pickable(doc), PathCache(), (50, 50), 0) is None
    assert shapes_in_rect(_pickable(doc), PathCache(), (0, 0, 500, 500)) == set()


def test_text_is_hit_on_glyphs():
    doc = _doc([TextShape(1, 10, 100, "H", 80, FILLED)])
    cache = PathCache()
    bounds = cache.bounds(doc.layers[0].shapes[0])
    left_stem = (bounds.left() + 3, bounds.centerY())
    assert shape_at(_pickable(doc), cache, left_stem, 0) == 1
    assert shape_at(_pickable(doc), cache, (bounds.centerX(), bounds.top() + 2), 0) is None


def test_rect_selects_intersecting_shapes():
    doc = _doc(
        [
            RectShape(1, 0, 0, 50, 50, FILLED),
            EllipseShape(2, 200, 200, 30, 30, FILLED),
            RectShape(3, 400, 400, 50, 50, FILLED),
        ]
    )
    assert shapes_in_rect(_pickable(doc), PathCache(), (40, 40, 180, 180)) == {1, 2}


def test_rect_inside_unfilled_shape_misses_it():
    doc = _doc([RectShape(1, 0, 0, 200, 200, OUTLINED)])
    assert shapes_in_rect(_pickable(doc), PathCache(), (50, 50, 20, 20)) == set()
    assert shapes_in_rect(_pickable(doc), PathCache(), (-10, 50, 20, 20)) == {1}


def test_rect_accepts_negative_size():
    doc = _doc([RectShape(1, 0, 0, 50, 50, FILLED)])
    assert shapes_in_rect(_pickable(doc), PathCache(), (60, 60, -30, -30)) == {1}


def test_rect_near_curve_bounds_but_off_curve_misses():
    arc = PathShape(1, (MoveTo(0, 0), LineTo(100, 100)), Style(fill=None, stroke="#000", stroke_width=1))
    doc = _doc([arc])
    assert shapes_in_rect(_pickable(doc), PathCache(), (70, 0, 20, 20)) == set()
    assert shapes_in_rect(_pickable(doc), PathCache(), (40, 40, 20, 20)) == {1}


def test_click_on_10k_shapes_is_fast():
    shapes = [RectShape(i, (i % 100) * 5, (i // 100) * 5, 4, 4, FILLED) for i in range(10_000)]
    doc = _doc(shapes)
    cache = PathCache()
    shape_at(_pickable(doc), cache, (1, 1), 3)
    start = time.perf_counter()
    assert shape_at(_pickable(doc), cache, (1, 1), 3) == 0
    assert time.perf_counter() - start < 0.010


def test_rotated_rect_is_hit_in_world_space():
    rect = transforms.with_rotation(RectShape(1, 20, 40, 60, 20, Style(stroke=None)), 90)
    doc = _doc([rect])
    assert shape_at(_pickable(doc), PathCache(), (50, 25), 0) == 1
    assert shape_at(_pickable(doc), PathCache(), (25, 50), 0) is None


def test_composite_is_hit_on_its_result_only():
    outer = RectShape(1, 0, 0, 100, 100, Style(stroke=None))
    hole = RectShape(2, 30, 30, 40, 40, Style(stroke=None))
    ring = CompositeShape(10, (outer, hole), ("add", "subtract"), Style(stroke=None))
    doc = _doc([ring])
    assert shape_at(_pickable(doc), PathCache(), (10, 10), 0) == 10
    assert shape_at(_pickable(doc), PathCache(), (50, 50), 0) is None


def test_empty_composite_is_found_by_its_parts_bounds():
    square = RectShape(1, 0, 0, 100, 100, Style(stroke=None))
    empty = CompositeShape(10, (square, RectShape(2, 0, 0, 100, 100, Style(stroke=None))), ("add", "subtract"), Style())
    cache = PathCache()
    assert cache.get(empty).isEmpty()
    bounds = cache.bounds(empty)
    assert (bounds.left(), bounds.top(), bounds.right(), bounds.bottom()) == (0, 0, 100, 100)
    doc = _doc([empty])
    assert shape_at(_pickable(doc), cache, (50, 50), 0) == 10
    assert shapes_in_rect(_pickable(doc), cache, (90, 90, 20, 20)) == {10}


def test_evenodd_hole_is_not_hit():
    segments = rect_segments(0, 0, 100, 100) + rect_segments(30, 30, 40, 40)
    doc = _doc([PathShape(1, segments, Style(fill="#ff0000", stroke=None, fill_rule="evenodd"))])
    assert shape_at(_pickable(doc), PathCache(), (50, 50), 0) is None
    assert shape_at(_pickable(doc), PathCache(), (10, 10), 0) == 1


def test_dash_gaps_are_not_hit():
    style = Style(fill=None, stroke="#000000", stroke_width=4, dashes=(10.0, 10.0))
    doc = _doc([PathShape(1, (MoveTo(0, 50), LineTo(100, 50)), style)])
    assert shape_at(_pickable(doc), PathCache(), (5, 50), 0) == 1
    assert shape_at(_pickable(doc), PathCache(), (15, 50), 0) is None


def test_transparent_shapes_stay_pickable():
    doc = _doc([RectShape(1, 0, 0, 100, 100, Style(fill="#ff0000", stroke=None, opacity=0))])
    assert shape_at(_pickable(doc), PathCache(), (50, 50), 0) == 1


def test_square_caps_grow_the_bounds():
    butt = Style(fill=None, stroke="#000000", stroke_width=10)
    line = (MoveTo(0, 0), LineTo(100, 0))
    cache = PathCache()
    plain = cache.bounds(PathShape(1, line, butt))
    square = cache.bounds(PathShape(2, line, Style(fill=None, stroke="#000000", stroke_width=10, cap="square")))
    assert square.fRight > plain.fRight + 1


def _group_doc():
    group = GroupShape(1, (RectShape(2, 0, 0, 10, 10, FILLED), RectShape(3, 50, 50, 10, 10, FILLED)))
    return _doc([group])


def test_a_group_is_hit_where_its_shapes_are():
    doc, cache = _group_doc(), PathCache()
    assert shape_at(_pickable(doc), cache, (55, 55), 0) == 1
    assert shape_at(_pickable(doc), cache, (30, 30), 0) is None


def test_rubber_band_finds_a_group_through_any_shape():
    doc, cache = _group_doc(), PathCache()
    assert shapes_in_rect(_pickable(doc), cache, (45, 45, 20, 20)) == {1}
    assert shapes_in_rect(_pickable(doc), cache, (20, 20, 10, 10)) == set()


def test_group_bounds_are_its_shapes():
    group = _group_doc().layers[0].shapes[0]
    bounds = PathCache().geometry_bounds(group)
    assert (bounds.left(), bounds.top(), bounds.right(), bounds.bottom()) == (0, 0, 60, 60)


def test_a_hidden_group_child_is_not_hit_and_not_framed():
    group = GroupShape(1, (RectShape(2, 0, 0, 10, 10, FILLED), RectShape(3, 50, 50, 10, 10, FILLED, hidden=True)))
    doc, cache = _doc([group]), PathCache()
    assert shape_at(_pickable(doc), cache, (55, 55), 0) is None
    assert shape_at(_pickable(doc), cache, (5, 5), 0) == 1
    assert shapes_in_rect(_pickable(doc), cache, (45, 45, 20, 20)) == set()
    bounds = cache.geometry_bounds(group)
    assert (bounds.left(), bounds.top(), bounds.right(), bounds.bottom()) == (0, 0, 10, 10)
    assert (cache.bounds(group).right(), cache.bounds(group).bottom()) == (10, 10)


def test_a_group_with_every_child_hidden_keeps_its_full_bounds():
    children = (RectShape(2, 0, 0, 10, 10, FILLED, hidden=True), RectShape(3, 50, 50, 10, 10, FILLED, hidden=True))
    bounds = PathCache().geometry_bounds(GroupShape(1, children))
    assert (bounds.left(), bounds.top(), bounds.right(), bounds.bottom()) == (0, 0, 60, 60)


def test_hidden_and_locked_shapes_are_passed_over_by_point_hits():
    below = RectShape(1, 0, 0, 100, 100, FILLED)
    hidden = RectShape(2, 0, 0, 100, 100, FILLED, hidden=True)
    locked = RectShape(3, 0, 0, 100, 100, FILLED, locked=True)
    assert shape_at([below, hidden, locked], PathCache(), (50, 50), 0) == 1


def _masked(mask_type="clip", mask=None, **fields) -> GroupShape:
    content = RectShape(1, 0, 0, 100, 100, FILLED)
    mask = mask or RectShape(2, 20, 20, 40, 40, FILLED)
    return GroupShape(9, (content, mask), masking=Masking(mask_type, (mask.id,), **fields))


def test_masked_group_is_picked_only_inside_its_clip():
    group = _masked()
    assert shape_at([group], PathCache(), (30, 30), 0) == 9
    assert shape_at([group], PathCache(), (80, 80), 0) is None


def test_inverted_clip_is_picked_outside_the_hole():
    group = _masked(inverted=True)
    assert shape_at([group], PathCache(), (30, 30), 0) is None
    assert shape_at([group], PathCache(), (80, 80), 0) == 9


def test_mask_object_alone_is_not_pickable_in_an_opacity_mask():
    mask = RectShape(2, 300, 300, 40, 40, FILLED)
    group = _masked("luminance", mask)
    assert shape_at([group], PathCache(), (310, 310), 0) is None
    assert shape_at([group], PathCache(), (50, 50), 0) == 9


def test_marquee_uses_visible_area_of_masked_group():
    group = _masked()
    assert shapes_in_rect([group], PathCache(), (70, 70, 20, 20)) == set()
    assert shapes_in_rect([group], PathCache(), (25, 25, 5, 5)) == {9}


def test_entered_masked_group_children_are_picked_individually():
    group = _masked()
    assert shape_at(list(group.children), PathCache(), (80, 80), 0) == 1
    assert shape_at(list(group.children), PathCache(), (30, 30), 0) == 2


def test_selection_frame_and_snap_points_use_visible_content():
    from presstoshape.render.handles import selection_frame
    from presstoshape.tools.snapper import shape_points

    group = _masked(mask=RectShape(2, 20, 20, 40, 40, FILLED))
    frame = selection_frame([group], PathCache())
    assert frame.rect == (20, 20, 40, 40)
    assert len(shape_points(group)) == len(shape_points(group.children[0]))


def test_translate_and_scale_move_mask_region_with_the_group():
    from presstoshape.geometry.transforms import transform_shape, translate

    group = _masked("luminance", region=(10.0, 20.0, 30.0, 40.0))
    assert translate(group, 5, 6).masking.region == (15.0, 26.0, 30.0, 40.0)
    assert transform_shape(group, (2, 0, 0, 2, 0, 0)).masking.region == (20.0, 40.0, 60.0, 80.0)
    turned = transform_shape(group, (0, 1, -1, 0, 0, 0)).masking.region
    assert turned == (-60.0, 10.0, 40.0, 30.0)


def test_fresh_ids_keep_mask_membership(session):
    from presstoshape.editing.operations._document import with_fresh_ids

    session.state.document.next_id = 100
    copy = with_fresh_ids(session.state, [_masked()])[0]
    assert copy.masking.mask_ids == (copy.children[1].id,)
    assert copy.children[1].id >= 100
