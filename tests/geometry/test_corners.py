import math
from dataclasses import replace

import pytest

from presstoshape.geometry import corners, nodes, transforms
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, PathShape, Rounding, Style

SQUARE = rect_segments(0, 0, 100, 100)
OPEN = (MoveTo(0, 0), LineTo(100, 0), LineTo(100, 100))


def rounded_at(segments, rounding, *indices):
    out = list(segments)
    for i in indices:
        out[i] = replace(out[i], rounding=rounding)
    return tuple(out)


def sample(segments, steps=40):
    topo = nodes.Topology(segments)
    points = []
    for i, s in enumerate(segments):
        if isinstance(s, (LineTo, CubicTo)):
            points.extend(nodes._eval(segments, topo, i, k / steps) for k in range(steps + 1))
    return points


def test_without_roundings_the_same_tuple_comes_back():
    assert corners.rounded(SQUARE) is SQUARE
    assert not corners.has_rounding(SQUARE)


def test_round_corner_follows_the_circle():
    result = corners.rounded(rounded_at(SQUARE, Rounding(10), 2))
    arc = next(s for s in result if isinstance(s, CubicTo))
    assert (arc.x, arc.y) == pytest.approx((90, 100))
    piece = (MoveTo(100, 90), arc)
    for x, y in sample(piece):
        assert math.dist((x, y), (90, 90)) == pytest.approx(10, abs=0.03)
    # Tangent continuity: the arc leaves straight down and arrives heading left.
    assert arc.c1x == pytest.approx(100) and arc.c2y == pytest.approx(100)


def test_every_corner_of_a_closed_square_including_the_start():
    result = corners.rounded(rounded_at(SQUARE, Rounding(10), 0, 1, 2, 3))
    assert isinstance(result[0], MoveTo) and (result[0].x, result[0].y) == pytest.approx((10, 0))
    assert sum(isinstance(s, CubicTo) for s in result) == 4
    assert isinstance(result[-1], Close)
    for x, y in sample(result):
        assert -1e-9 <= x <= 100 + 1e-9 and -1e-9 <= y <= 100 + 1e-9


def test_open_ends_and_smooth_nodes_are_not_rounded():
    open_path = rounded_at(OPEN, Rounding(10), 0, 1, 2)
    result = corners.rounded(open_path)
    assert (result[0].x, result[0].y) == (0, 0) and (result[-1].x, result[-1].y) == pytest.approx((100, 100))
    assert sum(isinstance(s, CubicTo) for s in result) == 1
    smooth = (MoveTo(0, 0), CubicTo(0, 10, 10, 10, 20, 10), CubicTo(30, 10, 40, 0, 40, -10))
    assert corners.roundable(smooth) == set()
    assert corners.rounded(rounded_at(smooth, Rounding(5), 1)) == smooth


def test_limits_share_an_edge_and_keep_the_stored_radius():
    square = rounded_at(SQUARE, Rounding(80), 1, 2)
    assert corners.limited(square) == {1, 2}
    assert corners.drawn_radius(square, 1) == pytest.approx(50)
    result = corners.rounded(square)
    # The right edge is used up by both arcs: they meet halfway.
    ends = [(s.x, s.y) for s in result if isinstance(s, CubicTo)]
    assert ends[0] == pytest.approx((100, 50))
    assert square[1].rounding.radius == 80
    assert corners.limited(rounded_at(SQUARE, Rounding(10), 1, 2)) == set()


def test_chamfer_and_inverted():
    chamfer = corners.rounded(rounded_at(SQUARE, Rounding(10, "chamfer"), 2))
    assert LineTo(90, 100) in [LineTo(s.x, s.y) for s in chamfer if isinstance(s, LineTo)]
    assert not any(isinstance(s, CubicTo) for s in chamfer)
    inverted = corners.rounded(rounded_at(SQUARE, Rounding(10, "inverted"), 2))
    arc = next(s for s in inverted if isinstance(s, CubicTo))
    for x, y in sample((MoveTo(100, 90), arc)):
        assert math.dist((x, y), (100, 100)) == pytest.approx(10, abs=0.03)


def test_corner_next_to_curves_cuts_at_the_arc_length():
    curve = (MoveTo(0, 0), CubicTo(30, 20, 70, 20, 100, 0), LineTo(100, 100))
    result = corners.rounded(rounded_at(curve, Rounding(10), 1))
    first = result[1]
    assert isinstance(first, CubicTo) and first.x < 100
    # The outline stays connected and ends where the path ends.
    assert (result[-1].x, result[-1].y) == pytest.approx((100, 100))
    points = sample(result, 80)
    gaps = max(math.dist(a, b) for a, b in zip(points, points[1:]))
    assert gaps < 3


def test_degenerate_corners_stay_sharp():
    folded = (MoveTo(0, 0), LineTo(100, 0), LineTo(0, 0))
    assert corners.roundable(folded) == set()
    zero = (MoveTo(0, 0), LineTo(0, 0), LineTo(100, 0), LineTo(100, 100))
    corners.rounded(rounded_at(zero, Rounding(5), 1, 2))


def test_widget_and_radius_for_are_inverse():
    square = rounded_at(SQUARE, Rounding(30), 2)
    (wx, wy) = corners.widget(square, 2, 1.0)
    distance = math.dist((wx, wy), (100, 100))
    assert corners.radius_for(square, 2, distance) == pytest.approx(30)
    # Small roundings keep the widget at the minimum distance.
    assert math.dist(corners.widget(SQUARE, 2, 8.0), (100, 100)) == pytest.approx(8)
    assert corners.radius_for(SQUARE, 2, -3) == 0
    assert corners.widget(OPEN, 0, 8.0) is None


def test_outline_rounds_paths():
    path = PathShape(1, rounded_at(SQUARE, Rounding(10), 0), Style())
    assert transforms.outline(path) == corners.rounded(path.segments)
    moved = transforms.translate(path, 5, 5)
    assert moved.segments[0].rounding == Rounding(10)
