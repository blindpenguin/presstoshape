import math

import pytest

from presstoshape.geometry.aspect import fitted_rect
from presstoshape.models.shapes import Aspect

ALIGNS = [f"x{x}Y{y}" for x in ("Min", "Mid", "Max") for y in ("Min", "Mid", "Max")]
FRACTION = {"Min": 0.0, "Mid": 0.5, "Max": 1.0}
SOURCES = {"wide": (200, 100), "tall": (100, 200), "square": (100, 100)}
VIEWPORTS = {"wide": (300, 100), "tall": (100, 300), "square": (100, 100)}


@pytest.mark.parametrize("align", ALIGNS)
@pytest.mark.parametrize("slice_", [False, True])
@pytest.mark.parametrize("source", SOURCES)
@pytest.mark.parametrize("viewport", VIEWPORTS)
def test_fitted_rect_matches_definition(align, slice_, source, viewport):
    source_width, source_height = SOURCES[source]
    width, height = VIEWPORTS[viewport]
    rect, clipped = fitted_rect(source_width, source_height, 10, 20, width, height, Aspect(align, slice_))
    scale_x, scale_y = width / source_width, height / source_height
    scale = max(scale_x, scale_y) if slice_ else min(scale_x, scale_y)
    expected_width, expected_height = source_width * scale, source_height * scale
    expected_x = 10 + (width - expected_width) * FRACTION[align[1:4]]
    expected_y = 20 + (height - expected_height) * FRACTION[align[5:8]]
    assert rect == pytest.approx((expected_x, expected_y, expected_width, expected_height))
    assert clipped is slice_


@pytest.mark.parametrize("slice_", [False, True])
def test_none_fills_the_viewport_without_clip(slice_):
    rect, clipped = fitted_rect(200, 100, 5, 6, 40, 70, Aspect("none", slice_))
    assert rect == (5, 6, 40, 70)
    assert clipped is False


def test_meet_letterboxes_and_slice_overflows():
    meet, _ = fitted_rect(200, 100, 0, 0, 100, 100, Aspect("xMidYMid"))
    assert meet == (0, 25, 100, 50)
    cover, clipped = fitted_rect(200, 100, 0, 0, 100, 100, Aspect("xMidYMid", True))
    assert cover == (-50, 0, 200, 100)
    assert clipped


@pytest.mark.parametrize(
    "sizes",
    [
        (0, 100, 0, 0, 10, 10),
        (100, 0, 0, 0, 10, 10),
        (100, 100, 0, 0, 0, 10),
        (100, 100, 0, 0, 10, -1),
        (math.nan, 100, 0, 0, 10, 10),
        (100, 100, math.inf, 0, 10, 10),
        (100, 100, 0, 0, math.inf, 10),
    ],
)
def test_empty_or_non_finite_sizes_give_an_empty_rect(sizes):
    rect, clipped = fitted_rect(*sizes, Aspect("xMidYMid"))
    assert rect[2] == 0.0 and rect[3] == 0.0
    assert all(math.isfinite(value) for value in rect)
    assert not clipped
