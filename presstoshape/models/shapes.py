"""Immutable shape/geometry data. Frozen so undo snapshots can share shapes and views can diff by equality."""

from dataclasses import dataclass
from typing import Literal


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


@dataclass(frozen=True)
class Style:
    fill: str | None = "#3b82f6"
    stroke: str | None = "#18181b"
    stroke_width: float = 2.0


@dataclass(frozen=True)
class RectShape:
    id: int
    x: float
    y: float
    width: float
    height: float
    style: Style
    transform: Transform = IDENTITY_TRANSFORM


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
