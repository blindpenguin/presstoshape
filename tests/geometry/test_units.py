import pytest

from presstoshape.geometry.units import UNITS, convert, from_px, to_px


@pytest.mark.parametrize("dpi, width, height", [(72, 595.28, 841.89), (96, 793.70, 1122.52), (300, 2480.31, 3507.87)])
def test_a4_in_pixels(dpi, width, height):
    assert to_px(210, "mm", dpi) == pytest.approx(width, abs=0.01)
    assert to_px(297, "mm", dpi) == pytest.approx(height, abs=0.01)


def test_physical_units_agree():
    assert convert(1, "in", "mm", 300) == pytest.approx(25.4)
    assert convert(1, "in", "pt", 96) == pytest.approx(72)
    assert convert(10, "mm", "cm", 72) == pytest.approx(1)
    assert convert(210, "mm", "in", 1) == pytest.approx(8.2677, abs=1e-4)


def test_px_is_identity_whatever_the_dpi():
    assert to_px(123.4, "px", 300) == 123.4
    assert from_px(123.4, "px", 72) == 123.4


@pytest.mark.parametrize("unit", UNITS)
def test_round_trips(unit):
    assert from_px(to_px(42.42, unit, 300), unit, 300) == pytest.approx(42.42)
