"""Immutable shape/geometry data. Frozen so undo snapshots can share shapes and views can diff by equality."""

from dataclasses import dataclass


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


@dataclass(frozen=True)
class EllipseShape:
    id: int
    cx: float
    cy: float
    rx: float
    ry: float
    style: Style


@dataclass(frozen=True)
class PathShape:
    id: int
    segments: tuple[Segment, ...]
    style: Style


@dataclass(frozen=True)
class TextShape:
    id: int
    x: float
    y: float
    text: str
    font_size: float
    style: Style


Shape = RectShape | EllipseShape | PathShape | TextShape
