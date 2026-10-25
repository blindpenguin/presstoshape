import math
from dataclasses import replace

import pytest

from presstoshape.geometry import nodes, path_edit
from presstoshape.geometry.pen_paths import PenNode, pen_segments
from presstoshape.geometry.segments import ellipse_segments, rect_segments
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, Rounding

RECT = rect_segments(0, 0, 10, 10)
ELLIPSE = ellipse_segments(0, 0, 10, 5)
OPEN = (MoveTo(0, 0), LineTo(10, 0), LineTo(20, 10), LineTo(30, 10))
# A kinked open curve: node 1 has both handles, pointing at 90° to each other.
KINK = (MoveTo(0, 0), CubicTo(0, 10, 10, 10, 20, 10), CubicTo(20, 20, 30, 0, 30, -10))
COMPOUND = (*RECT, MoveTo(2, 2), LineTo(8, 2), LineTo(5, 8), Close())
PEN = pen_segments(
    [PenNode((0, 0)), PenNode((10, 0), (5, -5), (15, 5)), PenNode((20, 0)), PenNode((10, 10), None, (5, 10))],
    closed=True,
)


def sample(segments, steps=24):
    """Points along the drawn outline, for comparing shapes regardless of segment layout."""
    topo = nodes.Topology(segments)
    out = []
    for i, s in enumerate(segments):
        drawn = isinstance(s, (LineTo, CubicTo)) or (isinstance(s, Close) and topo.subpath_of[i].alias is None)
        if drawn:
            out.extend(nodes._eval(segments, topo, i, k / steps) for k in range(steps + 1))
    return out


def same_shape(a, b):
    pa, pb = sample(a), sample(b)
    return len(pa) == len(pb) and all(math.dist(p, q) < 1e-9 for p, q in zip(pa, pb))


def info(segments, index):
    return next(n for n in nodes.nodes(segments) if n.index == index)


def handles(segments, index):
    return [nodes.control_point(segments, ref) for ref in info(segments, index).controls]


@pytest.mark.parametrize("segments", [RECT, ELLIPSE, OPEN, KINK, COMPOUND, PEN])
def test_subs_round_trip(segments):
    edited = path_edit.from_subs(path_edit.to_subs(segments))
    assert edited.segments == segments
    assert edited.index_map == {n.index: n.index for n in nodes.nodes(segments)}


def test_subs_of_closed_paths():
    subs = path_edit.to_subs(COMPOUND)
    assert [(len(s.anchors), len(s.edges), s.closed) for s in subs] == [(4, 4, True), (3, 3, True)]
    ellipse = path_edit.to_subs(ELLIPSE)[0]
    assert len(ellipse.anchors) == 4 and all(edge is not None for edge in ellipse.edges)


def test_explicit_closing_line_is_written_as_close():
    explicit = (MoveTo(0, 0), LineTo(10, 0), LineTo(10, 10), LineTo(0, 0), Close())
    edited = path_edit.from_subs(path_edit.to_subs(explicit))
    assert edited.segments == (MoveTo(0, 0), LineTo(10, 0), LineTo(10, 10), Close())
    assert same_shape(edited.segments, explicit)


def test_smooth_aligns_two_handles_keeping_their_lengths():
    lengths = [math.dist(h, (20, 10)) for h in handles(KINK, 1)]
    smoothed = path_edit.set_node_type(KINK, {1}, "smooth").segments
    assert not info(KINK, 1).smooth and info(smoothed, 1).smooth
    assert [math.dist(h, (20, 10)) for h in handles(smoothed, 1)] == pytest.approx(lengths)
    # Between the incoming handle's opposite (right) and the outgoing one (down): diagonal.
    assert (smoothed[2].c1x, smoothed[2].c1y) == pytest.approx((20 + 10 / math.sqrt(2), 10 + 10 / math.sqrt(2)))


def test_symmetric_evens_the_handle_lengths():
    uneven = (MoveTo(0, 0), CubicTo(0, 10, 10, 10, 20, 10), CubicTo(40, 10, 50, 0, 50, -10))
    result = path_edit.set_node_type(uneven, {1}, "symmetric").segments
    a, b = (math.dist(h, (20, 10)) for h in handles(result, 1))
    assert a == pytest.approx(b) == pytest.approx(15)
    assert info(result, 1).smooth


def test_smooth_on_lines_uses_the_neighbour_direction_and_thirds():
    result = path_edit.set_node_type(OPEN, {1}, "smooth").segments
    assert isinstance(result[1], CubicTo) and isinstance(result[2], CubicTo)
    assert isinstance(result[3], LineTo)
    direction = (20 / math.hypot(20, 10), 10 / math.hypot(20, 10))
    arm_in, arm_out = (result[1].c2x - 10, result[1].c2y), (result[2].c1x - 10, result[2].c1y)
    assert math.hypot(*arm_in) == pytest.approx(10 / 3)
    assert math.hypot(*arm_out) == pytest.approx(math.hypot(10, 10) / 3)
    assert arm_out[0] / math.hypot(*arm_out) == pytest.approx(direction[0])
    # The far ends keep the straight shape near the unchanged neighbours.
    assert (result[1].c1x, result[1].c1y) == pytest.approx((10 / 3, 0))
    assert info(result, 1).smooth


def test_smoothing_a_whole_polygon_makes_every_node_smooth():
    result = path_edit.set_node_type(RECT, {0, 1, 2, 3}, "smooth").segments
    assert all(n.smooth for n in nodes.nodes(result))


def test_end_nodes_only_lose_the_corner_flag():
    flagged = (MoveTo(0, 0, corner=True), *OPEN[1:])
    result = path_edit.set_node_type(flagged, {0, 3}, "smooth").segments
    assert result == OPEN


def test_corner_pulls_the_handles_into_the_node():
    result = path_edit.set_node_type(ELLIPSE, {0, 2}, "corner").segments
    for index, point in ((0, (10, 0)), (2, (-10, 0))):
        assert all(h == pytest.approx(point) for h in handles(result, index))
        assert not info(result, index).smooth
    # The other end of each segment keeps its handle, so the neighbours stay smooth curves.
    assert [n.smooth for n in nodes.nodes(result)] == [False, True, False, True]
    back = path_edit.set_node_type(result, {0, 2}, "smooth").segments
    assert all(n.smooth for n in nodes.nodes(back))


def test_corner_on_both_ends_makes_a_line():
    curved = path_edit.make_curves(RECT, {0, 1, 2, 3}).segments
    result = path_edit.set_node_type(curved, {0, 1, 2, 3}, "corner").segments
    assert result == (
        MoveTo(0, 0, corner=True),
        LineTo(10, 0, corner=True),
        LineTo(10, 10, corner=True),
        LineTo(0, 10, corner=True),
        Close(),
    )


def test_corner_on_a_line_node_only_sets_the_flag():
    result = path_edit.set_node_type(OPEN, {1}, "corner").segments
    assert result[1].corner and same_shape(result, OPEN)


def test_degenerate_node_is_left_unchanged():
    folded = (MoveTo(0, 0), LineTo(10, 0), LineTo(0, 0))
    assert path_edit.set_node_type(folded, {1}, "smooth").segments == folded


def test_make_curves_keeps_the_shape_only_between_chosen_nodes():
    result = path_edit.make_curves(RECT, {0, 1, 2}).segments
    assert [type(s).__name__ for s in result] == ["MoveTo", "CubicTo", "CubicTo", "LineTo", "Close"]
    assert same_shape(result, RECT)


def test_make_curves_on_the_closing_segment():
    result = path_edit.make_curves(RECT, {3, 0}).segments
    assert isinstance(result[4], CubicTo) and isinstance(result[5], Close)
    assert same_shape(result, RECT)


def test_make_lines_between_chosen_nodes():
    result = path_edit.make_lines(ELLIPSE, {0, 1}).segments
    assert isinstance(result[1], LineTo)
    assert all(isinstance(s, CubicTo) for s in result[2:5])
    assert path_edit.make_lines(ELLIPSE, {0, 2}).segments == ELLIPSE


def test_selection_helpers():
    assert path_edit.end_nodes(OPEN) == {0, 3}
    assert path_edit.end_nodes(COMPOUND) == set()
    assert path_edit.has_edge_between(RECT, {3, 0}) and not path_edit.has_edge_between(RECT, {0, 2})
    assert path_edit.has_line_between(RECT, {0, 1}) and not path_edit.has_curve_between(RECT, {0, 1})
    assert path_edit.has_curve_between(ELLIPSE, {1, 2})


# --- break, delete segment, open and close ---------------------------------------


def subs_of(segments):
    return [([a.point for a in sub.anchors], sub.closed) for sub in path_edit.to_subs(segments)]


def test_break_opens_a_closed_subpath_at_the_node():
    edited = path_edit.break_at(RECT, {2})
    assert subs_of(edited.segments) == [([(10, 10), (0, 10), (0, 0), (10, 0), (10, 10)], False)]
    assert same_shape_points(edited.segments, RECT)
    assert edited.focus == {0, 4}


def same_shape_points(a, b):
    """Same set of outline sample points (segment order and direction may differ)."""
    rounded = lambda points: sorted((round(x, 6), round(y, 6)) for x, y in points)  # noqa: E731
    return set(rounded(sample(a))) == set(rounded(sample(b)))


def test_break_splits_an_open_subpath_into_two_of_the_same_path():
    edited = path_edit.break_at(OPEN, {1, 2})
    assert subs_of(edited.segments) == [
        ([(0, 0), (10, 0)], False),
        ([(10, 0), (20, 10)], False),
        ([(20, 10), (30, 10)], False),
    ]
    assert edited.focus == {1, 2, 3, 4}


def test_break_ignores_end_nodes_and_keeps_curves():
    assert path_edit.break_at(OPEN, {0, 3}).segments == OPEN
    edited = path_edit.break_at(ELLIPSE, {1, 3})
    assert len(path_edit.to_subs(edited.segments)) == 2
    assert same_shape_points(edited.segments, ELLIPSE)


def test_break_in_compound_path_touches_only_that_subpath():
    edited = path_edit.break_at(COMPOUND, {6})
    assert [closed for _points, closed in subs_of(edited.segments)] == [True, False]


def test_delete_segment_opens_a_closed_subpath():
    edited = path_edit.delete_segments(RECT, {1, 2})
    assert subs_of(edited.segments) == [([(10, 10), (0, 10), (0, 0), (10, 0)], False)]


def test_delete_closing_segment():
    edited = path_edit.delete_segments(RECT, {3, 0})
    assert subs_of(edited.segments) == [([(0, 0), (10, 0), (10, 10), (0, 10)], False)]


def test_delete_segment_splits_an_open_subpath_and_drops_single_nodes():
    edited = path_edit.delete_segments(OPEN, {1, 2})
    assert subs_of(edited.segments) == [([(0, 0), (10, 0)], False), ([(20, 10), (30, 10)], False)]
    assert subs_of(path_edit.delete_segments(OPEN, {0, 1}).segments) == [([(10, 0), (20, 10), (30, 10)], False)]
    assert path_edit.delete_segments(OPEN[:2], {0, 1}) is None


def test_delete_two_segments_of_a_closed_subpath():
    edited = path_edit.delete_segments(RECT, {0, 1, 2, 3})
    assert edited is None
    edited = path_edit.delete_segments(RECT, {0, 1, 3})
    assert subs_of(edited.segments) == [([(10, 0), (10, 10), (0, 10)], False)]


def test_close_adds_a_straight_segment_or_merges_coincident_ends():
    closed = path_edit.close_subpaths(OPEN).segments
    assert closed == (*OPEN, Close())
    loop = (MoveTo(0, 0), CubicTo(0, 5, 5, 10, 10, 10), LineTo(10, 0), CubicTo(5, -2, 2, -1, 0, 0))
    merged = path_edit.close_subpaths(loop).segments
    assert [n.index for n in nodes.nodes(merged)] == [0, 1, 2]
    assert same_shape(merged, (*loop, Close()))


def test_close_only_subpaths_with_chosen_nodes():
    two = (*OPEN, MoveTo(0, 20), LineTo(10, 20), LineTo(10, 30))
    edited = path_edit.close_subpaths(two, {5})
    assert [closed for _points, closed in subs_of(edited.segments)] == [False, True]


def test_open_breaks_closed_subpaths_at_their_first_node():
    edited = path_edit.open_subpaths(COMPOUND)
    assert subs_of(edited.segments) == [
        ([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], False),
        ([(2, 2), (8, 2), (5, 8), (2, 2)], False),
    ]
    assert same_shape(edited.segments, COMPOUND)


# --- reverse ----------------------------------------------------------------------


@pytest.mark.parametrize("segments", [RECT, ELLIPSE, OPEN, KINK, COMPOUND, PEN])
def test_reverse_keeps_the_shape_and_twice_is_identity(segments):
    once = path_edit.reverse(segments).segments
    assert same_shape_points(once, segments)
    assert path_edit.reverse(once).segments == path_edit.from_subs(path_edit.to_subs(segments)).segments


def test_reverse_keeps_the_closed_start_and_flips_order():
    assert subs_of(path_edit.reverse(RECT).segments) == [([(0, 0), (0, 10), (10, 10), (10, 0)], True)]
    assert subs_of(path_edit.reverse(OPEN).segments) == [([(30, 10), (20, 10), (10, 0), (0, 0)], False)]


def test_reverse_only_chosen_subpaths_and_maps_indices():
    edited = path_edit.reverse(COMPOUND, {6})
    assert edited.segments[:5] == COMPOUND[:5]
    assert edited.index_map[6] == 7 and edited.index_map[7] == 6


# --- join -----------------------------------------------------------------------

TWO = (MoveTo(0, 0), LineTo(10, 0), MoveTo(20, 0), CubicTo(25, 5, 30, 5, 30, 0))


def test_join_ends_of_one_subpath_closes_it():
    edited = path_edit.join_ends(OPEN, 0, 3, with_segment=True)
    assert edited.segments == (*OPEN, Close())
    assert edited.focus == {0, 3}


def test_merge_ends_of_one_subpath_at_their_midpoint():
    edited = path_edit.join_ends(OPEN, 3, 0, with_segment=False)
    assert subs_of(edited.segments) == [([(15, 5), (20, 10), (10, 0)], True)]
    assert edited.focus == {0}
    assert path_edit.join_ends(OPEN[:2], 0, 1, with_segment=False) is None


@pytest.mark.parametrize(
    "a, b, points",
    [
        (1, 2, [(0, 0), (10, 0), (20, 0), (30, 0)]),
        (2, 1, [(0, 0), (10, 0), (20, 0), (30, 0)]),
        (0, 2, [(10, 0), (0, 0), (20, 0), (30, 0)]),
        (1, 3, [(0, 0), (10, 0), (30, 0), (20, 0)]),
        (0, 3, [(10, 0), (0, 0), (30, 0), (20, 0)]),
    ],
)
def test_join_two_subpaths_with_a_segment_in_every_direction(a, b, points):
    edited = path_edit.join_ends(TWO, a, b, with_segment=True)
    [(joined, closed)] = subs_of(edited.segments)
    assert not closed
    assert joined == points or joined == points[::-1]
    assert same_shape_points(path_edit.delete_segments(edited.segments, edited.focus).segments, TWO)


def test_merging_two_subpaths_keeps_their_handles():
    edited = path_edit.join_ends(TWO, 1, 2, with_segment=False)
    assert subs_of(edited.segments) == [([(0, 0), (15, 0), (30, 0)], False)]
    # The curve's first handle moved with its node, from (25, 5) by (-5, 0).
    assert edited.segments[2] == CubicTo(20, 5, 30, 5, 30, 0)
    assert edited.focus == {1}


def test_join_refuses_nodes_that_are_not_open_ends():
    assert path_edit.join_ends(OPEN, 1, 3, with_segment=True) is None
    assert path_edit.join_ends(RECT, 0, 1, with_segment=True) is None
    assert path_edit.join_ends(OPEN, 0, 0, with_segment=True) is None


def test_join_across_two_paths_through_combine():
    other = (MoveTo(40, 0), LineTo(50, 0))
    combined = path_edit.combine([OPEN, other])
    edited = path_edit.join_ends(combined, 3, len(OPEN) + 1, with_segment=True)
    assert subs_of(edited.segments) == [([(0, 0), (10, 0), (20, 10), (30, 10), (50, 0), (40, 0)], False)]


# --- combine and split ------------------------------------------------------------


def test_combine_and_split_are_inverse():
    parts = path_edit.split(COMPOUND)
    assert parts == [RECT, COMPOUND[5:]]
    assert path_edit.combine(parts) == COMPOUND


def test_split_drops_lone_moves():
    assert path_edit.split((MoveTo(5, 5), *OPEN)) == [OPEN]


# --- roundings ------------------------------------------------------------------------

R = Rounding(4.0)


def rounded_at(segments, *indices):
    out = list(segments)
    for i in indices:
        out[i] = replace(out[i], rounding=R)
    return tuple(out)


def roundings(segments):
    return {i for i, s in enumerate(segments) if getattr(s, "rounding", None) is not None}


def test_roundings_kept_by_corner_reverse_close_and_combine():
    square = rounded_at(RECT, 0, 2)
    assert roundings(path_edit.set_node_type(square, {0}, "corner").segments) == {0, 2}
    assert roundings(path_edit.reverse(square).segments) == {0, 2}
    assert roundings(path_edit.close_subpaths(rounded_at(OPEN, 1)).segments) == {1}
    assert roundings(path_edit.combine([square, rounded_at(OPEN, 1)])) == {0, 2, 6}
    assert [roundings(part) for part in path_edit.split(path_edit.combine([square, square]))] == [{0, 2}, {0, 2}]


def test_roundings_cleared_by_smooth_break_and_merge():
    square = rounded_at(RECT, 0, 2)
    assert roundings(path_edit.set_node_type(square, {2}, "smooth").segments) == {0}
    assert roundings(path_edit.break_at(square, {2}).segments) == {2}
    assert roundings(path_edit.break_at(rounded_at(OPEN, 1, 2), {1}).segments) == {3}
    merged = path_edit.join_ends(rounded_at(OPEN, 0, 3), 0, 3, with_segment=False)
    assert roundings(merged.segments) == set()
