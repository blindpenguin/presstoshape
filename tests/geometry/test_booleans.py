import pytest

from presstoshape.geometry import booleans
from presstoshape.geometry.segments import ellipse_segments, rect_segments
from presstoshape.models.shapes import CubicTo, MoveTo
from tests.helpers import bbox

A = rect_segments(0, 0, 10, 10)
B = rect_segments(5, 5, 10, 10)


def _area(segments) -> float:
    return booleans._to_skia(segments).area


def test_union_of_overlapping_squares_covers_both():
    a = rect_segments(0, 0, 10, 10)
    b = rect_segments(5, 5, 10, 10)
    result = booleans.combine_parts([(a, "add"), (b, "add")])
    assert sum(isinstance(s, MoveTo) for s in result) == 1
    assert bbox(result) == (0, 0, 15, 15)


def test_difference_cuts_top_out_of_bottom():
    a = rect_segments(0, 0, 10, 10)
    b = rect_segments(5, -5, 10, 20)
    assert bbox(booleans.combine_parts([(a, "add"), (b, "subtract")])) == (0, 0, 5, 10)


def test_difference_of_fully_covered_shape_is_empty():
    a = rect_segments(2, 2, 2, 2)
    b = rect_segments(0, 0, 10, 10)
    assert booleans.combine_parts([(a, "add"), (b, "subtract")]) == ()


def test_union_with_ellipse_keeps_curves():
    a = ellipse_segments(0, 0, 10, 10)
    b = rect_segments(0, -5, 20, 10)
    result = booleans.combine_parts([(a, "add"), (b, "add")])
    assert any(isinstance(s, CubicTo) for s in result)
    assert bbox(result) == pytest.approx((-10, -10, 20, 10), abs=0.01)


# --- combine_parts --------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode, area",
    [("add", 175), ("subtract", 75), ("intersect", 25), ("exclude", 150)],
)
def test_combine_parts_each_mode(mode, area):
    assert _area(booleans.combine_parts([(A, "add"), (B, mode)])) == pytest.approx(area)


def test_first_part_is_the_base_whatever_its_mode():
    assert booleans.combine_parts([(A, "subtract"), (B, "add")]) == booleans.combine_parts([(A, "add"), (B, "add")])


def test_parts_apply_in_order():
    c = rect_segments(0, 0, 3, 3)
    # (A intersect B) is the 5x5 overlap; adding C afterwards brings back C's 3x3 corner. Applied first, the
    # intersect would have cut C away.
    result = booleans.combine_parts([(A, "add"), (B, "intersect"), (c, "add")])
    assert _area(result) == pytest.approx(25 + 9)


def test_non_overlapping_intersect_is_empty():
    far = rect_segments(100, 100, 5, 5)
    assert booleans.combine_parts([(A, "add"), (far, "intersect")]) == ()


def test_exclude_of_three_fills_the_triple_overlap_again():
    c = rect_segments(2, 2, 10, 10)
    result = booleans.combine_parts([(A, "add"), (B, "exclude"), (c, "exclude")])
    # The square 5..10 x 5..10 is covered three times, so it's filled.
    assert booleans._to_skia(result).contains((7, 7))
    assert not booleans._to_skia(result).contains((3, 3))


def test_empty_and_single_part():
    assert booleans.combine_parts([]) == ()
    assert _area(booleans.combine_parts([(A, "intersect")])) == pytest.approx(100)


# --- split_regions --------------------------------------------------------------------


def _contours(segments) -> int:
    return sum(isinstance(segment, MoveTo) for segment in segments)


def test_disjoint_squares_are_two_regions():
    outline = rect_segments(0, 0, 5, 5) + rect_segments(10, 0, 5, 5)
    regions = booleans.split_regions(outline)
    assert len(regions) == 2
    assert {bbox(region) for region in regions} == {(0, 0, 5, 5), (10, 0, 15, 5)}


def test_square_with_hole_stays_one_region():
    ring = booleans.combine_parts([(rect_segments(0, 0, 10, 10), "add"), (rect_segments(3, 3, 4, 4), "subtract")])
    (region,) = booleans.split_regions(ring)
    assert _contours(region) == 2
    assert _area(region) == pytest.approx(84)


def test_island_inside_hole_is_its_own_region():
    ring = booleans.combine_parts([(rect_segments(0, 0, 10, 10), "add"), (rect_segments(2, 2, 6, 6), "subtract")])
    island = rect_segments(4, 4, 2, 2)
    regions = booleans.split_regions(booleans.combine_parts([(ring, "add"), (island, "add")]))
    assert len(regions) == 2
    assert sorted(_contours(region) for region in regions) == [1, 2]


def test_empty_outline_has_no_regions():
    assert booleans.split_regions(()) == []


# --- divide -----------------------------------------------------------------------------


def test_two_overlapping_squares_divide_into_three_pieces():
    pieces = booleans.divide([A, B])
    assert len(pieces) == 3
    by_area = sorted((round(_area(segments)), top) for segments, top in pieces)
    # Bottom-only L (75, top 0), overlap (25, top 1), top-only L (75, top 1).
    assert by_area == [(25, 1), (75, 0), (75, 1)]


def test_disconnected_parts_become_separate_pieces():
    ring = booleans.combine_parts([(rect_segments(0, 0, 10, 10), "add"), (rect_segments(3, 3, 4, 4), "subtract")])
    bar = rect_segments(-2, 4, 14, 2)
    pieces = booleans.divide([ring, bar])
    ring_only = [segments for segments, top in pieces if top == 0]
    # The bar cuts the ring into an upper and a lower part.
    assert len(ring_only) == 2
    assert all(_contours(segments) == 1 for segments in ring_only)


def test_identical_squares_give_one_piece():
    pieces = booleans.divide([A, A])
    assert [(round(_area(segments)), top) for segments, top in pieces] == [(100, 1)]


def test_slivers_are_dropped():
    nearly_same = rect_segments(0, 0, 10, 10.00001)
    pieces = booleans.divide([A, nearly_same])
    assert all(abs(_area(segments)) >= booleans.MIN_PIECE_AREA for segments, _ in pieces)
    assert len(pieces) == 1


def test_divide_twenty_shapes_quickly():
    import time

    outlines = [rect_segments(i * 3, (i % 4) * 3, 10, 10) for i in range(20)]
    start = time.perf_counter()
    pieces = booleans.divide(outlines)
    assert time.perf_counter() - start < 1.0
    assert pieces
