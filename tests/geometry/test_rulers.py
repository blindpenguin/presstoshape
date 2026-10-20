import pytest

from presstoshape.geometry.rulers import ruler_ticks


def _labels(ticks):
    return [tick.label for tick in ticks if tick.label is not None]


def test_px_ruler_at_100_percent_labels_round_hundreds():
    ticks = ruler_ticks(0, 1.0, 500, "px", 96)
    assert _labels(ticks)[:4] == ["0", "100", "200", "300"]
    majors = [tick.screen for tick in ticks if tick.major]
    assert majors[:2] == [0, 100]


def test_labels_stay_readable_when_zooming():
    for zoom in (0.1, 0.37, 1, 4.2, 30):
        majors = [tick.screen for tick in ruler_ticks(-123, zoom, 1000, "px", 96) if tick.major]
        spacing = majors[1] - majors[0]
        assert 60 <= spacing <= 300


def test_minor_ticks_are_not_too_dense():
    ticks = ruler_ticks(0, 1.0, 300, "mm", 96)
    gaps = [b.screen - a.screen for a, b in zip(ticks, ticks[1:])]
    assert min(gaps) >= 5 - 1e-9


def test_mm_ruler_labels_in_mm_and_starts_before_zero():
    ticks = ruler_ticks(-100, 2.0, 400, "mm", 96)
    assert "0" in _labels(ticks) and "-10" in _labels(ticks)
    zero = next(tick for tick in ticks if tick.label == "0")
    assert zero.screen == pytest.approx(200)


def test_fractional_steps_get_decimals():
    labels = _labels(ruler_ticks(0, 400.0, 600, "in", 96))
    assert "0.01" in labels or "0.02" in labels
