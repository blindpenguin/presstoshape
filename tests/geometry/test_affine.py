import math

import pytest

from veccy.geometry import affine


def _close(p, q, eps=1e-9):
    return all(abs(a - b) <= eps for a, b in zip(p, q))


def test_compose_applies_inner_first():
    m = affine.compose(affine.translation(10, 0), affine.scaling(2, 2))
    assert affine.apply(m, 1, 1) == (12, 2)


def test_invert_round_trip():
    m = affine.compose(affine.rotation(0.7, 5, 3), affine.scaling(2, -3, 1, 1))
    assert _close(affine.compose(m, affine.invert(m)), affine.IDENTITY)
    assert _close(affine.apply(affine.invert(m), *affine.apply(m, 4, 9)), (4, 9))


def test_invert_singular_raises():
    with pytest.raises(ValueError):
        affine.invert(affine.scaling(0, 1))


def test_rotation_keeps_center_fixed():
    m = affine.rotation(math.pi / 2, 10, 20)
    assert _close(affine.apply(m, 10, 20), (10, 20))
    assert _close(affine.apply(m, 11, 20), (10, 21))


def test_as_rotation_round_trip():
    angle, cx, cy = affine.as_rotation(affine.rotation(math.radians(30), 7, -4))
    assert (angle, cx, cy) == pytest.approx((30, 7, -4))


def test_as_rotation_half_turn():
    angle, cx, cy = affine.as_rotation(affine.rotation(math.pi, 2, 3))
    assert abs(angle) == pytest.approx(180)
    assert (cx, cy) == pytest.approx((2, 3))


def test_as_rotation_identity():
    assert affine.as_rotation(affine.IDENTITY) == (0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "m",
    [affine.scaling(2, 2), (1.0, 0.0, 0.5, 1.0, 0.0, 0.0), affine.translation(3, 0), affine.scaling(-1, 1)],
)
def test_as_rotation_rejects_non_rotations(m):
    assert affine.as_rotation(m) is None


def test_is_identity_tolerance():
    assert affine.is_identity((1.0, 1e-12, 0.0, 1.0, 0.0, -1e-12))
    assert not affine.is_identity(affine.translation(1e-6, 0))
