import pytest

from presstoshape.geometry.align import align_offsets, distribute_offsets, union

BOXES = [(0, 0, 10, 10), (30, 5, 20, 40), (12, 50, 4, 4)]


@pytest.mark.parametrize(
    "edge, expected",
    [
        ("left", [(0, 0), (-30, 0), (-12, 0)]),
        ("right", [(40, 0), (0, 0), (34, 0)]),
        ("hcenter", [(20, 0), (-15, 0), (11, 0)]),
        ("top", [(0, 0), (0, -5), (0, -50)]),
        ("bottom", [(0, 44), (0, 9), (0, 0)]),
        ("vcenter", [(0, 22), (0, 2), (0, -25)]),
    ],
)
def test_align_to_the_union_of_the_boxes(edge, expected):
    assert align_offsets(BOXES, edge, union(BOXES)) == pytest.approx(expected)


def test_align_to_another_reference():
    assert align_offsets([(10, 10, 20, 20)], "hcenter", (0, 0, 100, 100)) == [(30, 0)]


def test_distribute_gaps_keeps_the_outer_boxes_and_order():
    boxes = [(100, 0, 10, 10), (0, 0, 10, 10), (30, 0, 30, 10)]
    offsets = distribute_offsets(boxes, "gaps_x")
    moved = [box[0] + offset[0] for box, offset in zip(boxes, offsets)]
    assert moved == pytest.approx([100, 0, 40])
    assert all(offset[1] == 0 for offset in offsets)


def test_distribute_centres_vertically():
    boxes = [(0, 0, 10, 10), (0, 90, 10, 20), (0, 20, 10, 2)]
    offsets = distribute_offsets(boxes, "centers_y")
    centres = [box[1] + box[3] / 2 + offset[1] for box, offset in zip(boxes, offsets)]
    assert centres == pytest.approx([5, 100, 52.5])


def test_distribute_gaps_overlap_evenly_when_too_wide():
    boxes = [(0, 0, 50, 10), (5, 0, 50, 10), (20, 0, 50, 10)]
    offsets = distribute_offsets(boxes, "gaps_x")
    starts = [box[0] + offset[0] for box, offset in zip(boxes, offsets)]
    # 150 wide in a 70 span: each neighbour overlaps the previous one by 40.
    assert starts == pytest.approx([0, 10, 20])


def test_fewer_than_three_boxes_do_not_move():
    assert distribute_offsets([(0, 0, 1, 1), (5, 0, 1, 1)], "gaps_x") == [(0, 0), (0, 0)]
