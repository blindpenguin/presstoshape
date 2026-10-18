"""Pure geometry helpers over the model's segment types. No Qt — booleans go through skia-pathops."""

import math
from collections.abc import Callable
from dataclasses import replace

import pathops

from veccy.models.shapes import (
    Close,
    CubicTo,
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Segment,
    Shape,
    TextShape,
)

Point = tuple[float, float]

# Control-point distance that best approximates a quarter circle with one cubic.
_KAPPA = 0.5522847498307936

_BOOLEAN_OPS = {
    "union": pathops.PathOp.UNION,
    "difference": pathops.PathOp.DIFFERENCE,
}


def box_from_drag(start: Point, end: Point, square: bool = False) -> tuple[float, float, float, float]:
    w, h = end[0] - start[0], end[1] - start[1]
    if square:
        side = max(abs(w), abs(h))
        w, h = math.copysign(side, w), math.copysign(side, h)
    return min(start[0], start[0] + w), min(start[1], start[1] + h), abs(w), abs(h)


def smooth_segments(points: list[Point]) -> tuple[Segment, ...]:
    """Catmull-Rom spline through `points`, emitted as cubic beziers."""
    segments: list[Segment] = [MoveTo(*points[0])]
    n = len(points)
    for i in range(n - 1):
        p0, p1, p2 = points[max(i - 1, 0)], points[i], points[i + 1]
        p3 = points[min(i + 2, n - 1)]
        segments.append(
            CubicTo(
                p1[0] + (p2[0] - p0[0]) / 6,
                p1[1] + (p2[1] - p0[1]) / 6,
                p2[0] - (p3[0] - p1[0]) / 6,
                p2[1] - (p3[1] - p1[1]) / 6,
                p2[0],
                p2[1],
            )
        )
    return tuple(segments)


def rect_segments(x: float, y: float, w: float, h: float) -> tuple[Segment, ...]:
    return (MoveTo(x, y), LineTo(x + w, y), LineTo(x + w, y + h), LineTo(x, y + h), Close())


def ellipse_segments(cx: float, cy: float, rx: float, ry: float) -> tuple[Segment, ...]:
    kx, ky = rx * _KAPPA, ry * _KAPPA
    return (
        MoveTo(cx + rx, cy),
        CubicTo(cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry),
        CubicTo(cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy),
        CubicTo(cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry),
        CubicTo(cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy),
        Close(),
    )


def quad_to_cubic(start: Point, control: Point, end: Point) -> CubicTo:
    return CubicTo(
        start[0] + 2 / 3 * (control[0] - start[0]),
        start[1] + 2 / 3 * (control[1] - start[1]),
        end[0] + 2 / 3 * (control[0] - end[0]),
        end[1] + 2 / 3 * (control[1] - end[1]),
        end[0],
        end[1],
    )


def outline(shape: Shape) -> tuple[Segment, ...] | None:
    """Shape geometry as path segments, or None for shapes without vector outline (text)."""
    match shape:
        case RectShape(x=x, y=y, width=w, height=h):
            return rect_segments(x, y, w, h)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            return ellipse_segments(cx, cy, rx, ry)
        case PathShape(segments=segments):
            return segments
        case TextShape():
            return None


def transform_segments(segments: tuple[Segment, ...], fn: Callable[[float, float], Point]) -> tuple[Segment, ...]:
    """Maps every point through `fn`. Exact for affine `fn` since lines and cubics are affine-invariant."""
    out: list[Segment] = []
    for s in segments:
        match s:
            case MoveTo(x, y):
                out.append(MoveTo(*fn(x, y)))
            case LineTo(x, y):
                out.append(LineTo(*fn(x, y)))
            case CubicTo(c1x, c1y, c2x, c2y, x, y):
                out.append(CubicTo(*fn(c1x, c1y), *fn(c2x, c2y), *fn(x, y)))
            case Close():
                out.append(s)
    return tuple(out)


def translate(shape: Shape, dx: float, dy: float) -> Shape:
    match shape:
        case RectShape() | TextShape():
            return replace(shape, x=shape.x + dx, y=shape.y + dy)
        case EllipseShape():
            return replace(shape, cx=shape.cx + dx, cy=shape.cy + dy)
        case PathShape():
            return replace(shape, segments=transform_segments(shape.segments, lambda x, y: (x + dx, y + dy)))


def boolean(outlines: list[tuple[Segment, ...]], op: str) -> tuple[Segment, ...]:
    """Folds `op` over outlines bottom-to-top: union merges all, difference cuts the rest out of the first."""
    result = _to_skia(outlines[0])
    for other in outlines[1:]:
        result = pathops.op(result, _to_skia(other), _BOOLEAN_OPS[op])
    return _from_skia(result)


def _to_skia(segments: tuple[Segment, ...]) -> pathops.Path:
    path = pathops.Path()
    for s in segments:
        match s:
            case MoveTo(x, y):
                path.moveTo(x, y)
            case LineTo(x, y):
                path.lineTo(x, y)
            case CubicTo(c1x, c1y, c2x, c2y, x, y):
                path.cubicTo(c1x, c1y, c2x, c2y, x, y)
            case Close():
                path.close()
    return path


def _from_skia(path: pathops.Path) -> tuple[Segment, ...]:
    # Skia works in float32; rounding drops the noise digits (5.667570114135742 -> 5.668).
    def pt(p: tuple[float, float]) -> Point:
        return round(p[0], 3), round(p[1], 3)

    out: list[Segment] = []
    current = start = (0.0, 0.0)
    for verb, points in path.segments:
        if verb == "moveTo":
            current = start = pt(points[0])
            out.append(MoveTo(*current))
        elif verb == "lineTo":
            current = pt(points[0])
            out.append(LineTo(*current))
        elif verb == "curveTo":
            c1, c2, end = (pt(p) for p in points)
            out.append(CubicTo(*c1, *c2, *end))
            current = end
        elif verb == "qCurveTo":
            # TrueType-style run: implied on-curve points sit midway between consecutive controls.
            *controls, end = (pt(p) for p in points)
            for i, control in enumerate(controls):
                if i == len(controls) - 1:
                    nxt = end
                else:
                    following = controls[i + 1]
                    nxt = ((control[0] + following[0]) / 2, (control[1] + following[1]) / 2)
                out.append(quad_to_cubic(current, control, nxt))
                current = nxt
        elif verb == "closePath":
            out.append(Close())
            current = start
    return tuple(out)
