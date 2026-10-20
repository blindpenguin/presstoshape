import pytest

from presstoshape.geometry.units import UNITS, convert, default_grid, from_px, grid_of, nudge_px, to_px
from presstoshape.models.app_state import Document
from presstoshape.models.layout import GridSettings


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


def test_nudge_steps_are_round_in_each_unit():
    assert nudge_px("px", 300) == 1
    assert nudge_px("mm", 96) == pytest.approx(to_px(0.5, "mm", 96))
    assert nudge_px("pt", 72) == pytest.approx(1)


def test_default_grids_are_round_in_each_unit():
    assert default_grid("px", 300) == GridSettings(10, 10)
    mm = default_grid("mm", 96)
    assert (from_px(mm.spacing, "mm", 96), mm.major_every) == (pytest.approx(5), 2)
    assert from_px(default_grid("in", 72).spacing, "in", 72) == pytest.approx(0.25)


def test_grid_of_prefers_the_documents_own_grid():
    document = Document(unit="mm", dpi=96)
    assert grid_of(document) == default_grid("mm", 96)
    document.grid = GridSettings(3.0, 7)
    assert grid_of(document) == GridSettings(3.0, 7)
