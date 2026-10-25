import pytest

from presstoshape.geometry import nodes
from presstoshape.geometry.pen_paths import PenNode, mirrored, pen_segments, with_drag
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo


def test_corners_make_straight_lines():
    segments = pen_segments([PenNode((0, 0)), PenNode((10, 0)), PenNode((10, 10))])
    assert segments == (MoveTo(0, 0), LineTo(10, 0), LineTo(10, 10))


def test_smooth_middle_node_curves_both_sides_and_is_smooth():
    middle = with_drag(PenNode((10, 0)), (15, 5))
    segments = pen_segments([PenNode((0, 0)), middle, PenNode((20, 0))])
    assert segments == (MoveTo(0, 0), CubicTo(0, 0, 5, -5, 10, 0), CubicTo(15, 5, 20, 0, 20, 0))
    assert [info.smooth for info in nodes.nodes(segments)] == [False, True, False]


def test_corner_after_smooth_node_has_its_control_on_the_end_node():
    start = with_drag(PenNode((0, 0)), (5, 5))
    segments = pen_segments([start, PenNode((10, 0)), PenNode((20, 0))])
    assert segments[1] == CubicTo(5, 5, 10, 0, 10, 0)
    assert segments[2] == LineTo(20, 0)


def test_closed_straight_path_ends_with_close_only():
    segments = pen_segments([PenNode((0, 0)), PenNode((10, 0)), PenNode((10, 10))], closed=True)
    assert segments == (MoveTo(0, 0), LineTo(10, 0), LineTo(10, 10), Close())
    assert len(nodes.nodes(segments)) == 3


def test_closed_curved_path_lists_the_first_node_once():
    first = with_drag(PenNode((0, 0)), (0, -5))
    segments = pen_segments([first, PenNode((10, 0)), PenNode((10, 10))], closed=True)
    assert segments[-2] == CubicTo(10, 10, 0, 5, 0, 0)
    assert isinstance(segments[-1], Close)
    infos = nodes.nodes(segments)
    assert [info.point for info in infos] == [(0, 0), (10, 0), (10, 10)]
    assert infos[0].smooth


def test_single_or_no_node():
    assert pen_segments([]) == ()
    assert pen_segments([PenNode((1, 2))], closed=True) == (MoveTo(1, 2),)


def test_mirrored():
    assert mirrored((10, 10), (15, 12)) == (5, 8)


def test_with_drag_mirrors_or_keeps_incoming():
    node = with_drag(PenNode((0, 0)), (4, 3))
    assert node == PenNode((0, 0), (-4, -3), (4, 3))
    broken = with_drag(node, (0, 10), mirror=False)
    assert broken == PenNode((0, 0), (-4, -3), (0, 10))


def test_with_drag_onto_the_node_clears_handles():
    assert with_drag(PenNode((0, 0), (1, 1), (-1, -1)), (0, 0)) == PenNode((0, 0))


@pytest.mark.parametrize("closed", [False, True])
def test_broken_handles_are_not_smooth(closed):
    middle = with_drag(with_drag(PenNode((10, 0)), (15, 5)), (10, 8), mirror=False)
    infos = nodes.nodes(pen_segments([PenNode((0, 0)), middle, PenNode((20, 0))], closed))
    assert not infos[1].smooth
