import pytest

from presstoshape.geometry import booleans
from presstoshape.geometry.segments import ellipse_segments, rect_segments
from presstoshape.models.shapes import CubicTo, MoveTo
from tests.helpers import bbox


def test_union_of_overlapping_squares_covers_both():
    a = rect_segments(0, 0, 10, 10)
    b = rect_segments(5, 5, 10, 10)
    result = booleans.boolean([a, b], "union")
    assert sum(isinstance(s, MoveTo) for s in result) == 1
    assert bbox(result) == (0, 0, 15, 15)



def test_difference_cuts_top_out_of_bottom():
    a = rect_segments(0, 0, 10, 10)
    b = rect_segments(5, -5, 10, 20)
    assert bbox(booleans.boolean([a, b], "difference")) == (0, 0, 5, 10)



def test_difference_of_fully_covered_shape_is_empty():
    a = rect_segments(2, 2, 2, 2)
    b = rect_segments(0, 0, 10, 10)
    assert booleans.boolean([a, b], "difference") == ()



def test_union_with_ellipse_keeps_curves():
    a = ellipse_segments(0, 0, 10, 10)
    b = rect_segments(0, -5, 20, 10)
    result = booleans.boolean([a, b], "union")
    assert any(isinstance(s, CubicTo) for s in result)
    assert bbox(result) == pytest.approx((-10, -10, 20, 10), abs=0.01)
