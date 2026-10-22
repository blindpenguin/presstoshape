"""viewBox, preserveAspectRatio, the fitting matrix and the overflow check."""

import math

import pytest

from presstoshape.formats.svg_viewport import (
    DEFAULT,
    INVALID,
    Aspect,
    escapes,
    fit,
    is_finite,
    parse_aspect,
    parse_view_box,
)
from presstoshape.geometry.affine import apply
from presstoshape.models.shapes import EllipseShape, GroupShape, LineTo, MoveTo, PathShape, RectShape, Style, TextShape


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, None),
        ("0 0 100 50", (0, 0, 100, 50)),
        ("  0,0,100,50  ", (0, 0, 100, 50)),
        ("0 , 0 ,100 , 50", (0, 0, 100, 50)),
        ("-10 -20 1e2 .5", (-10, -20, 100, 0.5)),
        ("10-5 0 3 4", INVALID),
        ("0 0 100", INVALID),
        ("0 0 100 50 7", INVALID),
        ("a b c d", INVALID),
        ("", INVALID),
        ("0 0 1e999 5", INVALID),
        ("0 0 0 50", (0, 0, 0, 50)),
        ("0 0 -4 50", (0, 0, -4, 50)),
    ],
)
def test_parse_view_box(text, expected):
    assert parse_view_box(text) == expected


def test_view_box_sign_separates_numbers():
    assert parse_view_box("0 0 10 -5") == (0, 0, 10, -5)
    assert parse_view_box("0 0 10,-5") == (0, 0, 10, -5)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (None, None),
        ("none", Aspect("none")),
        ("xMidYMid", DEFAULT),
        ("xMinYMax slice", Aspect("xMinYMax", True)),
        ("xMaxYMid meet", Aspect("xMaxYMid")),
        ("defer xMinYMin slice", Aspect("xMinYMin", True)),
        ("  none  ", Aspect("none")),
        ("xmidymid", INVALID),
        ("XMidYMid", INVALID),
        ("xMidYMid cover", INVALID),
        ("xMidYMid meet extra", INVALID),
        ("none slice", Aspect("none", True)),
        ("defer", INVALID),
        ("", INVALID),
        ("xMidYMi", INVALID),
    ],
)
def test_parse_aspect(text, expected):
    assert parse_aspect(text) == expected


@pytest.mark.parametrize("x", ["xMin", "xMid", "xMax"])
@pytest.mark.parametrize("y", ["YMin", "YMid", "YMax"])
@pytest.mark.parametrize("slice", [False, True])
def test_every_align_value_parses(x, y, slice):
    assert parse_aspect(f"{x}{y} {'slice' if slice else 'meet'}") == Aspect(x + y, slice)


def corner(matrix, x, y):
    return tuple(round(v, 9) for v in apply(matrix, x, y))


def test_meet_wide_viewport_centres_horizontally():
    matrix = fit((0, 0, 100, 100), 200, 100, DEFAULT)
    assert corner(matrix, 0, 0) == (50, 0)
    assert corner(matrix, 100, 100) == (150, 100)


@pytest.mark.parametrize(
    ("align", "origin"),
    [
        ("xMinYMin", (0, 0)),
        ("xMidYMin", (50, 0)),
        ("xMaxYMin", (100, 0)),
    ],
)
def test_meet_horizontal_alignment(align, origin):
    assert corner(fit((0, 0, 100, 100), 200, 100, Aspect(align)), 0, 0) == origin


@pytest.mark.parametrize(
    ("align", "origin"),
    [
        ("xMinYMin", (0, 0)),
        ("xMinYMid", (0, 50)),
        ("xMinYMax", (0, 100)),
    ],
)
def test_meet_vertical_alignment_in_tall_viewport(align, origin):
    assert corner(fit((0, 0, 100, 100), 100, 200, Aspect(align)), 0, 0) == origin


def test_slice_covers_the_viewport():
    matrix = fit((0, 0, 100, 100), 200, 100, Aspect("xMidYMid", True))
    assert matrix[0] == matrix[3] == 2
    assert corner(matrix, 0, 0) == (0, -50)
    assert corner(matrix, 100, 100) == (200, 150)


def test_slice_min_aligns_to_top_left():
    matrix = fit((0, 0, 100, 100), 200, 100, Aspect("xMinYMin", True))
    assert corner(matrix, 0, 0) == (0, 0)


def test_none_stretches_each_axis():
    matrix = fit((10, 20, 100, 50), 200, 200, Aspect("none"))
    assert (matrix[0], matrix[3]) == (2, 4)
    assert corner(matrix, 10, 20) == (0, 0)
    assert corner(matrix, 110, 70) == (200, 200)


def test_view_box_origin_moves_to_viewport_origin():
    matrix = fit((100, 100, 100, 100), 100, 100, DEFAULT)
    assert corner(matrix, 100, 100) == (0, 0)
    assert corner(matrix, 150, 150) == (50, 50)


def test_fit_with_extreme_values_can_be_checked_for_finiteness():
    assert is_finite(fit((0, 0, 1, 1), 10, 10, DEFAULT))
    assert not is_finite((math.inf, 0, 0, 1, 0, 0))


def square(x, y, size=10.0):
    return RectShape(1, x, y, size, size, Style())


def test_escapes_inside_and_outside():
    assert not escapes([square(0, 0)], 0, 0, 10, 10)
    assert escapes([square(5, 0)], 0, 0, 10, 10)
    assert escapes([square(-1, 0)], 0, 0, 10, 10)


def test_escapes_recurses_into_groups():
    assert escapes([GroupShape(2, (square(20, 20),))], 0, 0, 10, 10)
    assert not escapes([GroupShape(2, (square(0, 0),))], 0, 0, 10, 10)


def test_escapes_uses_the_shape_transform():
    rotated = RectShape(1, 0, 0, 10, 10, Style(), transform=(0.0, 1.0, -1.0, 0.0, 0.0, 0.0))
    assert escapes([rotated], 0, 0, 10, 10)


def test_escapes_tolerates_rounding():
    assert not escapes([square(0, 0, 10 + 1e-9)], 0, 0, 10, 10)


def test_escapes_checks_path_points_and_ellipses():
    path = PathShape(1, (MoveTo(0, 0), LineTo(30, 0)), Style())
    assert escapes([path], 0, 0, 10, 10)
    assert not escapes([EllipseShape(2, 5, 5, 5, 5, Style())], 0, 0, 10, 10)


def test_text_is_ignored():
    assert not escapes([TextShape(1, 500, 500, "far", 16.0, Style())], 0, 0, 10, 10)
