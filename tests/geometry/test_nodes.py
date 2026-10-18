import pytest

from presstoshape.geometry import nodes
from presstoshape.geometry.segments import ellipse_segments, rect_segments
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo

RECT = rect_segments(0, 0, 10, 10)
ELLIPSE = ellipse_segments(0, 0, 10, 5)
OPEN = (MoveTo(0, 0), LineTo(10, 0), LineTo(20, 0), LineTo(30, 10))
SMOOTH = (MoveTo(0, 0), CubicTo(0, 10, 10, 10, 20, 0), CubicTo(30, -10, 40, -10, 50, 0))


def _sample(segments, steps=50):
    """Points along the outline, for comparing shapes regardless of segment layout."""
    path = []
    for i, s in enumerate(segments):
        if isinstance(s, (LineTo, CubicTo)):
            for k in range(steps + 1):
                path.append(nodes._eval(segments, nodes._Topology(segments), i, k / steps))
    return path


def test_rect_has_four_nodes_without_controls():
    info = nodes.nodes(RECT)
    assert [n.index for n in info] == [0, 1, 2, 3]
    assert all(n.controls == () for n in info)


def test_ellipse_closing_endpoint_is_alias_of_moveto():
    info = nodes.nodes(ELLIPSE)
    assert [n.index for n in info] == [0, 1, 2, 3]
    first = info[0]
    assert set(first.controls) == {(4, 2), (1, 1)}
    assert all(n.smooth for n in info)


def test_move_node_moves_attached_controls_and_alias():
    moved = nodes.move_nodes(ELLIPSE, {0}, 5, 0)
    assert (moved[0].x, moved[4].x) == (15, 15)
    assert moved[1].c1x == ELLIPSE[1].c1x + 5
    assert moved[4].c2x == ELLIPSE[4].c2x + 5
    assert moved[2] == ELLIPSE[2]


def test_move_nodes_ignores_invalid_indices():
    assert nodes.move_nodes(RECT, {4, 99}, 5, 5) == RECT


def test_smooth_control_keeps_opposite_collinear_with_own_length():
    moved = nodes.move_control(SMOOTH, (1, 2), (20, 30))
    assert (moved[1].c2x, moved[1].c2y) == (20, 30)
    # Anchor (20, 0); opposite was (30, -10), length sqrt(200), now straight down from the anchor.
    assert (moved[2].c1x, moved[2].c1y) == pytest.approx((20, -200**0.5))


def test_alt_control_drag_breaks_smoothness():
    moved = nodes.move_control(SMOOTH, (1, 2), (20, 30), keep_smooth=False)
    assert moved[2] == SMOOTH[2]


def test_insert_node_on_cubic_keeps_shape():
    inserted, index = nodes.insert_node(SMOOTH, 1, 0.5)
    assert index == 1 and len(inserted) == len(SMOOTH) + 1
    assert (inserted[1].x, inserted[1].y) == pytest.approx(nodes._eval(SMOOTH, nodes._Topology(SMOOTH), 1, 0.5))
    original = _sample(SMOOTH, 400)
    for p in _sample(inserted, 20):
        assert min(abs(p[0] - q[0]) + abs(p[1] - q[1]) for q in original) < 0.2


def test_insert_node_on_implicit_closing_line():
    inserted, index = nodes.insert_node(RECT, 4, 0.5)
    assert inserted[index] == LineTo(0, 5) and isinstance(inserted[-1], Close)


def test_delete_middle_node_joins_neighbours():
    out = nodes.delete_nodes(OPEN, {1})
    assert out == (MoveTo(0, 0), LineTo(20, 0), LineTo(30, 10))


def test_delete_curve_node_merges_into_one_cubic():
    out = nodes.delete_nodes(SMOOTH, {1})
    assert out == (MoveTo(0, 0), CubicTo(0, 10, 40, -10, 50, 0))


def test_delete_closed_node_keeps_closed():
    out = nodes.delete_nodes(RECT, {0})
    assert out == (MoveTo(10, 0), LineTo(10, 10), LineTo(0, 10), Close())


def test_delete_to_fewer_than_two_nodes_drops_subpath():
    two = (MoveTo(0, 0), LineTo(5, 5), MoveTo(10, 10), LineTo(20, 20), LineTo(30, 30))
    out = nodes.delete_nodes(two, {1})
    assert out == (MoveTo(10, 10), LineTo(20, 20), LineTo(30, 30))


def test_delete_everything_returns_none():
    assert nodes.delete_nodes(OPEN, {0, 1, 2, 3}) is None


def test_nearest_on_path():
    index, t, dist = nodes.nearest_on_path(OPEN, (15, 2))
    assert index == 2 and t == pytest.approx(0.5, abs=1e-3) and dist == pytest.approx(2, abs=1e-3)
    index, t, _ = nodes.nearest_on_path(RECT, (-1, 5))
    assert index == 4 and t == pytest.approx(0.5, abs=1e-3)
