import pytest

from presstoshape.geometry.boxes import constrain_angle


@pytest.mark.parametrize(
    ("point", "expected"),
    [
        ((10, 1), (10, 0)),
        ((1, 10), (0, 10)),
        ((10, 9), (9.5, 9.5)),
        ((-10, 1), (-10, 0)),
        ((-10, -9), (-9.5, -9.5)),
        ((2, -20), (0, -20)),
    ],
)
def test_constrain_angle_projects_onto_45_degree_rays(point, expected):
    x, y = constrain_angle((0, 0), point)
    assert x == pytest.approx(expected[0]) and y == pytest.approx(expected[1])


def test_constrain_angle_is_relative_to_origin_and_step():
    assert constrain_angle((100, 100), (110, 101)) == pytest.approx((110, 100))
    assert constrain_angle((0, 0), (10, 3), step_deg=90) == pytest.approx((10, 0))
