"""Immutable shape/geometry data. Frozen so undo snapshots can share shapes and views can diff by equality."""

import math
from dataclasses import dataclass, replace
from typing import Literal, get_args


@dataclass(frozen=True)
class MoveTo:
    x: float
    y: float


@dataclass(frozen=True)
class LineTo:
    x: float
    y: float


@dataclass(frozen=True)
class CubicTo:
    c1x: float
    c1y: float
    c2x: float
    c2y: float
    x: float
    y: float


@dataclass(frozen=True)
class Close:
    pass


Segment = MoveTo | LineTo | CubicTo | Close

# Affine (a, b, c, d, e, f) as in SVG matrix(); applied on top of the shape's geometry.
Transform = tuple[float, float, float, float, float, float]
IDENTITY_TRANSFORM: Transform = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


FillRule = Literal["nonzero", "evenodd"]
LineCap = Literal["butt", "round", "square"]
LineJoin = Literal["miter", "round", "bevel"]
TextAnchor = Literal["start", "middle", "end"]


@dataclass(frozen=True)
class Style:
    """Paint of a shape. Defaults match SVG, so a style without the newer fields draws as SVG would."""

    fill: str | None = "#3b82f6"
    stroke: str | None = "#18181b"
    stroke_width: float = 2.0
    # Opacities are 0..1; `opacity` applies to the shape as a whole (fill and stroke flattened first).
    opacity: float = 1.0
    fill_opacity: float = 1.0
    stroke_opacity: float = 1.0
    fill_rule: FillRule = "nonzero"
    cap: LineCap = "butt"
    join: LineJoin = "miter"
    miter_limit: float = 4.0
    # Dash and gap lengths, always an even count; () is a solid line.
    dashes: tuple[float, ...] = ()
    dash_offset: float = 0.0


def _unit(value: float) -> float:
    return min(1.0, max(0.0, value)) if math.isfinite(value) else 1.0


def _dashes(values: tuple[float, ...]) -> tuple[float, ...]:
    """SVG rules: an odd list is repeated; negative values, non-finite values or a zero total mean solid."""
    if any(not math.isfinite(v) or v < 0 for v in values) or sum(values) <= 0:
        return ()
    values = tuple(float(v) for v in values)
    return values * 2 if len(values) % 2 else values


def sanitized(style: Style) -> Style:
    """`style` with every field in range: opacities clamped, unknown enum values reset, dashes normalized."""
    defaults = Style()
    return replace(
        style,
        stroke_width=max(0.0, style.stroke_width) if math.isfinite(style.stroke_width) else defaults.stroke_width,
        opacity=_unit(style.opacity),
        fill_opacity=_unit(style.fill_opacity),
        stroke_opacity=_unit(style.stroke_opacity),
        fill_rule=style.fill_rule if style.fill_rule in get_args(FillRule) else defaults.fill_rule,
        cap=style.cap if style.cap in get_args(LineCap) else defaults.cap,
        join=style.join if style.join in get_args(LineJoin) else defaults.join,
        miter_limit=max(1.0, style.miter_limit) if math.isfinite(style.miter_limit) else defaults.miter_limit,
        dashes=_dashes(tuple(style.dashes)),
        dash_offset=style.dash_offset if math.isfinite(style.dash_offset) else 0.0,
    )


@dataclass(frozen=True)
class RectShape:
    id: int
    x: float
    y: float
    width: float
    height: float
    style: Style
    transform: Transform = IDENTITY_TRANSFORM
    # Corner radii, clamped to half the width / height when drawn (as SVG does).
    rx: float = 0.0
    ry: float = 0.0


@dataclass(frozen=True)
class EllipseShape:
    id: int
    cx: float
    cy: float
    rx: float
    ry: float
    style: Style
    transform: Transform = IDENTITY_TRANSFORM


@dataclass(frozen=True)
class PathShape:
    id: int
    segments: tuple[Segment, ...]
    style: Style
    transform: Transform = IDENTITY_TRANSFORM


@dataclass(frozen=True)
class TextShape:
    id: int
    x: float
    y: float
    text: str
    font_size: float
    style: Style
    transform: Transform = IDENTITY_TRANSFORM
    # Which point of the line sits at (x, y), as SVG text-anchor.
    anchor: TextAnchor = "start"


# How a Composite part combines with everything below it. The bottom part is the base whatever its mode.
PartMode = Literal["add", "subtract", "intersect", "exclude"]


@dataclass(frozen=True)
class CompositeShape:
    """Parts combined bottom to top, each by its mode; painted as one outline in the Composite's style."""

    id: int
    parts: tuple["Shape", ...]
    # One per part; modes[0] is ignored because the first part is the base.
    modes: tuple[PartMode, ...]
    style: Style
    # Stays identity: transforms are applied to the parts.
    transform: Transform = IDENTITY_TRANSFORM


Shape = RectShape | EllipseShape | PathShape | TextShape | CompositeShape
