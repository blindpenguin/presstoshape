import random
import time

import pytest

from presstoshape.geometry.snapping import NO_SNAP, GridSpec, LineTarget, SnapTargets


def _edges():
    """An object spanning x 100..200, y 50..80."""
    xs = [LineTarget(100, "edge", (50, 80)), LineTarget(150, "centre", (50, 80)), LineTarget(200, "edge", (50, 80))]
    ys = [LineTarget(50, "edge", (100, 200)), LineTarget(65, "centre", (100, 200)), LineTarget(80, "edge", (100, 200))]
    return SnapTargets(xs, ys)


def test_point_snaps_per_axis_within_tolerance():
    result = _edges().snap_point((103, 300), 5)
    assert result.offset == (-3, 0)
    (hit,) = result.hits
    assert (hit.axis, hit.value, hit.target) == ("x", 100, "edge")
    assert _edges().snap_point((107, 300), 5) == NO_SNAP


def test_nearest_target_wins_and_axes_are_independent():
    result = _edges().snap_point((148, 79), 5)
    assert result.offset == (2, 1)
    assert {hit.target for hit in result.hits} == {"centre", "edge"}


def test_box_snaps_its_edges_and_centre():
    # A box 0..20 wide whose right edge is 2 short of x 100, centre close to nothing.
    result = _edges().snap_box((78, 300, 20, 10), 5)
    assert result.offset == (2, 0)
    hit = result.hits[0]
    # The feedback line reaches from the target object (y 50..80) to the box (y 300..310).
    assert hit.line == ((100, 50), (100, 310))


def test_box_centre_snaps_to_centre_line():
    # Centre 149 is 1 from the centre line; the edges are further from anything.
    result = _edges().snap_box((139, 0, 20, 5), 5)
    assert result.offset[0] == pytest.approx(1)
    assert result.hits[0].target == "centre"


def test_grid_rounds_from_its_origin_and_lines_win_ties():
    grid = GridSpec((5, 5), 10)
    assert SnapTargets(grid=grid).snap_point((18, 33), 3).offset == (-3, 2)
    targets = SnapTargets(xs=[LineTarget(25, "guide")], grid=grid)
    (hit,) = [hit for hit in targets.snap_point((24, 100), 3).hits if hit.axis == "x"]
    assert hit.target == "guide"


def test_nodes_snap_on_both_axes_first():
    targets = SnapTargets(xs=[LineTarget(10, "guide")], points=[(12, 40)])
    result = targets.snap_point((11, 38), 4)
    assert result.offset == (1, 2) and result.hits[0].target == "node"


def test_box_with_points_snaps_a_node_to_a_node():
    targets = SnapTargets(points=[(50, 50)])
    result = targets.snap_box((0, 0, 100, 100), 3, points=[(48, 51)])
    assert result.offset == (2, -1)


def test_many_targets_stay_fast():
    rng = random.Random(1)
    xs = [LineTarget(rng.uniform(0, 10_000), "edge", (0, 1)) for _ in range(10_000)]
    ys = [LineTarget(rng.uniform(0, 10_000), "edge", (0, 1)) for _ in range(10_000)]
    points = [(rng.uniform(0, 10_000), rng.uniform(0, 10_000)) for _ in range(10_000)]
    targets = SnapTargets(xs, ys, points, GridSpec((0, 0), 10))
    start = time.perf_counter()
    for index in range(1000):
        targets.snap_box((index * 7.3, index * 3.1, 40, 30), 4, points=[(index * 7.3, index * 3.1)])
    assert (time.perf_counter() - start) / 1000 < 0.002
