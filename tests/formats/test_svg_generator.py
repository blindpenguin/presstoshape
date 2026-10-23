"""Saved SVG must look the same in another renderer (resvg) as on our canvas."""

import importlib.util
import math
from pathlib import Path

import pytest

from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    GradientStop,
    GroupShape,
    LinearGradient,
    LineTo,
    Masking,
    MoveTo,
    PathShape,
    RadialGradient,
    RectShape,
    Style,
    TextShape,
)

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "svg_conformance.py"
_spec = importlib.util.spec_from_file_location("svg_conformance", _SCRIPT)
svg_conformance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(svg_conformance)

FILL = Style(fill="#2f6fd0", stroke="#202020", stroke_width=4)
NO_STROKE = Style(fill="#2f6fd0", stroke=None)
LINE = Style(fill=None, stroke="#c03020", stroke_width=12)


def _stroked(**options) -> Style:
    return Style(fill=None, stroke="#202020", **options)


def _blue(**options) -> Style:
    return Style(fill="#2f6fd0", **options)


def _square(x: float, y: float, size: float, clockwise: bool = True) -> tuple:
    corners = [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]
    if not clockwise:
        corners.reverse()
    first, *rest = corners
    return (MoveTo(*first), *(LineTo(*corner) for corner in rest), Close())


def _rotation(degrees: float, cx: float, cy: float) -> tuple:
    a = math.radians(degrees)
    cos, sin = math.cos(a), math.sin(a)
    return (cos, sin, -sin, cos, cx - cos * cx + sin * cy, cy - sin * cx - cos * cy)


def _doc(*shapes, layers: list[Layer] | None = None) -> Document:
    return Document(width=400, height=300, layers=layers or [Layer("Layer 1", shapes=list(shapes))])


_RGB = (GradientStop(0, "#d03030"), GradientStop(0.5, "#30a050"), GradientStop(1, "#2f6fd0"))
_FADE = (GradientStop(0, "#2f6fd0"), GradientStop(1, "#2f6fd0", 0.1))


def _gradient(**options) -> Style:
    return Style(fill=LinearGradient(0, 0, 1, 0, _RGB, **options), stroke=None)


_next_mask_group_id = iter(range(900, 1000))


def _masked(content, mask_type, mask, **fields) -> GroupShape:
    return GroupShape(
        next(_next_mask_group_id),
        (*content, *mask),
        masking=Masking(mask_type, tuple(shape.id for shape in mask), **fields),
    )


DOCUMENTS = {
    "basic shapes": _doc(
        RectShape(1, 20, 20, 120, 80, FILL),
        RectShape(2, 160, 20, 120, 80, FILL, rx=20, ry=12),
        EllipseShape(3, 340, 60, 40, 30, FILL),
        PathShape(4, (MoveTo(20, 200), CubicTo(80, 120, 140, 280, 200, 200), LineTo(260, 260)), LINE),
        PathShape(5, (MoveTo(280, 160), LineTo(380, 180), LineTo(320, 280), Close()), FILL),
    ),
    "fill rules": _doc(
        # Both contours run the same way: nonzero fills the hole, evenodd leaves it empty.
        PathShape(1, _square(20, 20, 160) + _square(60, 60, 80), NO_STROKE),
        PathShape(2, _square(220, 20, 160) + _square(260, 60, 80), _blue(stroke=None, fill_rule="evenodd")),
        PathShape(3, _square(20, 200, 90) + _square(40, 220, 50, clockwise=False), NO_STROKE),
    ),
    "text anchors": _doc(
        TextShape(1, 200, 60, "Start anchor", 28, NO_STROKE),
        TextShape(2, 200, 150, "Middle anchor", 28, NO_STROKE, anchor="middle"),
        TextShape(3, 200, 240, "End anchor", 28, NO_STROKE, anchor="end"),
    ),
    "group opacity": _doc(
        GroupShape(
            1,
            (RectShape(2, 40, 40, 180, 140, NO_STROKE), EllipseShape(3, 220, 160, 110, 90, Style(fill="#d03030"))),
            0.5,
        ),
    ),
    "composite": _doc(
        CompositeShape(
            1,
            (
                RectShape(2, 40, 40, 240, 200, FILL),
                EllipseShape(3, 280, 140, 90, 90, FILL),
                RectShape(4, 100, 100, 80, 80, FILL),
            ),
            ("add", "add", "subtract"),
            Style(fill="#30a050", stroke="#202020", stroke_width=3),
        ),
    ),
    "transforms": _doc(
        RectShape(1, 60, 60, 120, 60, FILL, transform=_rotation(30, 120, 90)),
        EllipseShape(2, 300, 90, 60, 30, FILL, transform=_rotation(-20, 300, 90)),
        RectShape(3, 60, 180, 100, 60, FILL, transform=(1, 0, 0.5, 1, -105, 0)),
        TextShape(4, 300, 240, "Turned", 30, NO_STROKE, transform=_rotation(15, 300, 240)),
    ),
    "opacities": _doc(
        RectShape(1, 20, 20, 360, 260, Style(fill="#f0c020", stroke=None)),
        RectShape(2, 40, 40, 140, 100, _blue(stroke="#202020", stroke_width=16, opacity=0.5)),
        RectShape(3, 220, 40, 140, 100, _blue(stroke="#202020", stroke_width=16, fill_opacity=0.3)),
        RectShape(4, 40, 170, 140, 100, _blue(stroke="#202020", stroke_width=16, stroke_opacity=0.4)),
    ),
    "stroke options": _doc(
        PathShape(1, (MoveTo(40, 40), LineTo(160, 40)), _stroked(stroke_width=20, cap="round")),
        PathShape(2, (MoveTo(220, 40), LineTo(340, 40)), _stroked(stroke_width=20, cap="square")),
        PathShape(3, (MoveTo(40, 160), LineTo(100, 90), LineTo(160, 160)), _stroked(stroke_width=20, join="round")),
        PathShape(4, (MoveTo(220, 160), LineTo(280, 90), LineTo(340, 160)), _stroked(stroke_width=20, join="bevel")),
        # The sharp corner exceeds miter limit 2 and falls back to a bevel.
        PathShape(5, (MoveTo(40, 280), LineTo(100, 200), LineTo(160, 280)), _stroked(stroke_width=14, miter_limit=2)),
        PathShape(
            6, (MoveTo(220, 240), LineTo(380, 240)), _stroked(stroke_width=10, dashes=(24, 12, 6, 12), dash_offset=8)
        ),
    ),
    "linear gradients": _doc(
        RectShape(1, 20, 20, 160, 100, _gradient()),
        RectShape(
            2, 220, 20, 160, 100, Style(fill=LinearGradient(0, 0, 0.3, 0.6, _RGB, spread="reflect"), stroke=None)
        ),
        RectShape(3, 20, 160, 160, 100, Style(fill=LinearGradient(0, 0, 0.25, 0, _RGB, spread="repeat"), stroke=None)),
        RectShape(4, 220, 160, 160, 100, Style(fill=LinearGradient(0.2, 0, 0.8, 0, _FADE), stroke=None)),
    ),
    "radial gradients": _doc(
        EllipseShape(1, 100, 100, 80, 60, Style(fill=RadialGradient(0.5, 0.5, 0.5, 0.5, 0.5, _RGB), stroke=None)),
        EllipseShape(2, 300, 100, 80, 60, Style(fill=RadialGradient(0.5, 0.5, 0.5, 0.25, 0.4, _RGB), stroke=None)),
        RectShape(
            3,
            20,
            180,
            160,
            100,
            Style(fill=RadialGradient(0.5, 0.5, 0.25, 0.5, 0.5, _RGB, spread="repeat"), stroke=None),
        ),
    ),
    "gradient units and transforms": _doc(
        RectShape(1, 20, 20, 160, 100, _gradient(units="userSpaceOnUse")),
        RectShape(
            2,
            220,
            20,
            160,
            100,
            Style(fill=LinearGradient(20, 0, 160, 0, _RGB, "userSpaceOnUse", "pad", (1, 0, 0, 1, 220, 0)), stroke=None),
        ),
        RectShape(3, 40, 160, 140, 80, _gradient(transform=(1, 0.5, 0, 1, 0, 0))),
        RectShape(
            4,
            220,
            160,
            140,
            80,
            Style(fill=LinearGradient(0, 0, 1, 0, _RGB), stroke=None),
            transform=_rotation(20, 290, 200),
        ),
    ),
    "gradient strokes": _doc(
        RectShape(1, 40, 40, 140, 100, Style(fill=None, stroke=LinearGradient(0, 0, 1, 0, _RGB), stroke_width=20)),
        PathShape(
            2,
            (MoveTo(220, 60), LineTo(380, 60), LineTo(380, 200)),
            Style(fill=None, stroke=LinearGradient(220, 0, 380, 0, _RGB, "userSpaceOnUse"), stroke_width=16),
        ),
    ),
    "clipping masks": _doc(
        _masked(
            [RectShape(1, 20, 20, 160, 120, Style(fill="#d03030", stroke=None))],
            "clip",
            [EllipseShape(2, 100, 80, 50, 40, NO_STROKE)],
        ),
        _masked(
            [RectShape(3, 220, 20, 160, 120, Style(fill="#30a050", stroke=None))],
            "clip",
            [EllipseShape(4, 300, 80, 50, 40, NO_STROKE)],
            inverted=True,
        ),
        _masked(
            [RectShape(5, 20, 160, 160, 120, Style(fill="#2f6fd0", stroke=None))],
            "clip",
            [PathShape(6, _square(40, 180, 120) + _square(70, 210, 60), _blue(stroke=None, fill_rule="evenodd"))],
        ),
        _masked(
            [RectShape(7, 220, 160, 160, 120, Style(fill="#d03030", stroke=None))],
            "clip",
            [RectShape(8, 230, 170, 60, 100, NO_STROKE), EllipseShape(9, 340, 220, 40, 40, NO_STROKE)],
        ),
    ),
    "opacity masks": _doc(
        _masked(
            [RectShape(1, 20, 20, 160, 120, Style(fill="#d03030", stroke=None))],
            "luminance",
            [
                RectShape(
                    2,
                    20,
                    20,
                    160,
                    120,
                    Style(
                        fill=LinearGradient(0, 0, 1, 0, (GradientStop(0, "#000000"), GradientStop(1, "#ffffff"))),
                        stroke=None,
                    ),
                )
            ],
        ),
        _masked(
            [RectShape(3, 220, 20, 160, 120, Style(fill="#2f6fd0", stroke=None))],
            "alpha",
            [EllipseShape(4, 300, 80, 60, 40, Style(fill="#000000", fill_opacity=0.5, stroke=None))],
        ),
        _masked(
            [RectShape(5, 20, 160, 160, 120, Style(fill="#30a050", stroke=None))],
            "luminance",
            [
                RectShape(6, 20, 160, 80, 120, Style(fill="#ffffff", stroke=None)),
                RectShape(7, 100, 160, 80, 120, Style(fill="#808080", stroke=None)),
            ],
        ),
        _masked(
            [RectShape(8, 220, 160, 160, 120, Style(fill="#d03030", stroke=None))],
            "luminance",
            [RectShape(9, 220, 160, 160, 120, Style(fill="#ffffff", stroke=None))],
            region=(250.0, 180.0, 100.0, 80.0),
        ),
    ),
    "hidden content": _doc(
        layers=[
            Layer(
                "Visible",
                shapes=[RectShape(1, 20, 20, 160, 120, FILL), RectShape(2, 220, 20, 160, 120, FILL, hidden=True)],
            ),
            Layer("Hidden", visible=False, shapes=[EllipseShape(3, 200, 220, 120, 60, FILL)]),
        ],
    ),
}


@pytest.mark.parametrize("name", list(DOCUMENTS))
def test_saved_svg_looks_the_same_in_resvg(name):
    assert svg_conformance.check_generator(DOCUMENTS[name]) < svg_conformance.THRESHOLD
