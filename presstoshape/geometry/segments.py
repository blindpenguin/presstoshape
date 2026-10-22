"""Building and mapping path segments (the model's MoveTo/LineTo/CubicTo/Close)."""

import math
from collections.abc import Callable

from presstoshape.geometry.boxes import Point
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment

# Control-point distance that best approximates a quarter circle with one cubic.
_KAPPA = 0.5522847498307936


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


def rect_segments(x: float, y: float, w: float, h: float, rx: float = 0.0, ry: float = 0.0) -> tuple[Segment, ...]:
    """Clockwise from the top-left; radii are clamped to half the size, and a zero radius gives sharp corners."""
    rx, ry = min(max(rx, 0.0), abs(w) / 2), min(max(ry, 0.0), abs(h) / 2)
    if rx <= 0 or ry <= 0:
        return (MoveTo(x, y), LineTo(x + w, y), LineTo(x + w, y + h), LineTo(x, y + h), Close())
    kx, ky = rx * _KAPPA, ry * _KAPPA
    right, bottom = x + w, y + h
    return (
        MoveTo(x + rx, y),
        LineTo(right - rx, y),
        CubicTo(right - rx + kx, y, right, y + ry - ky, right, y + ry),
        LineTo(right, bottom - ry),
        CubicTo(right, bottom - ry + ky, right - rx + kx, bottom, right - rx, bottom),
        LineTo(x + rx, bottom),
        CubicTo(x + rx - kx, bottom, x, bottom - ry + ky, x, bottom - ry),
        LineTo(x, y + ry),
        CubicTo(x, y + ry - ky, x + rx - kx, y, x + rx, y),
        Close(),
    )


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


def _cubic_extrema(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    """Parameters in (0, 1) where one coordinate of a cubic has a turning point."""
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = p1 - p0
    if abs(a) < 1e-12:
        roots = [-c / b] if abs(b) > 1e-12 else []
    else:
        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return []
        root = math.sqrt(discriminant)
        roots = [(-b + root) / (2 * a), (-b - root) / (2 * a)]
    return [t for t in roots if 0 < t < 1]


def segments_bounds(segments: tuple[Segment, ...]) -> tuple[float, float, float, float] | None:
    """Tight bounding box (x, y, width, height) of the drawn geometry, curve turning points included; None when
    there are no points."""
    xs: list[float] = []
    ys: list[float] = []
    current: Point | None = None
    start: Point | None = None
    for s in segments:
        match s:
            case MoveTo(x, y):
                current = start = (x, y)
                xs.append(x)
                ys.append(y)
            case LineTo(x, y):
                current = (x, y)
                xs.append(x)
                ys.append(y)
            case CubicTo(c1x, c1y, c2x, c2y, x, y):
                x0, y0 = current if current is not None else (c1x, c1y)
                for t in _cubic_extrema(x0, c1x, c2x, x) + _cubic_extrema(y0, c1y, c2y, y):
                    u = 1 - t
                    xs.append(u**3 * x0 + 3 * u * u * t * c1x + 3 * u * t * t * c2x + t**3 * x)
                    ys.append(u**3 * y0 + 3 * u * u * t * c1y + 3 * u * t * t * c2y + t**3 * y)
                current = (x, y)
                xs.append(x)
                ys.append(y)
            case Close():
                current = start
    if not xs:
        return None
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)
