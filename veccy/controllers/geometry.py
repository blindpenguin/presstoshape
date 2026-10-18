"""Pure geometry helpers over the model's segment types. No Qt — booleans go through skia-pathops."""

import math
from collections.abc import Callable
from dataclasses import replace

import pathops

from veccy.controllers import affine
from veccy.controllers.affine import Affine
from veccy.models.shapes import (
    IDENTITY_TRANSFORM,
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

_ANGLE_EPS = 1e-9
_SCALE_EPS = 1e-12
_ORTHO_EPS = 1e-9

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
    """Shape geometry as path segments with its transform applied, or None for text (no vector outline here)."""
    match shape:
        case RectShape(x=x, y=y, width=w, height=h):
            segments = rect_segments(x, y, w, h)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            segments = ellipse_segments(cx, cy, rx, ry)
        case PathShape(segments=segments):
            pass
        case TextShape():
            return None
    return _apply_affine(segments, shape.transform)


def _apply_affine(segments: tuple[Segment, ...], m: Affine) -> tuple[Segment, ...]:
    if m == IDENTITY_TRANSFORM:
        return segments
    return transform_segments(segments, lambda x, y: affine.apply(m, x, y))


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
        case PathShape():
            return replace(shape, segments=transform_segments(shape.segments, lambda x, y: (x + dx, y + dy)))
        case RectShape() | TextShape():
            moved = replace(shape, x=shape.x + dx, y=shape.y + dy)
        case EllipseShape():
            moved = replace(shape, cx=shape.cx + dx, cy=shape.cy + dy)
    if shape.transform == IDENTITY_TRANSFORM:
        return moved
    # Conjugate so the transform keeps acting about the moved geometry (rotation stays about the new center).
    shift = affine.translation(dx, dy)
    return replace(moved, transform=affine.compose(shift, affine.compose(shape.transform, affine.invert(shift))))


def _center(shape: RectShape | EllipseShape | TextShape) -> Point:
    match shape:
        case RectShape(x=x, y=y, width=w, height=h):
            return x + w / 2, y + h / 2
        case EllipseShape(cx=cx, cy=cy):
            return cx, cy
        case TextShape(x=x, y=y):
            return x, y


def _rotation_about(radians: float, center: Point) -> Affine:
    if abs(math.remainder(radians, math.tau)) < _ANGLE_EPS:
        return IDENTITY_TRANSFORM
    return affine.rotation(radians, *center)


def transform_shape(shape: Shape, m: Affine, min_extent: float = 0.0) -> Shape:
    """`shape` with `m` applied on top of its transform, in canonical form.

    Paths get the transform baked into their segments. Rect/ellipse keep axis scales in their size and only a
    rotation about their center in `transform`, unless the result is skewed (then the full matrix is kept). Text
    scales uniformly by the larger axis factor and keeps its rotation about the anchor. Raises ValueError when
    the result would be singular.
    """
    total = affine.compose(m, shape.transform)
    if isinstance(shape, PathShape):
        return replace(shape, segments=_apply_affine(shape.segments, total), transform=IDENTITY_TRANSFORM)
    a, b, c, d = total[:4]
    su, sv = math.hypot(a, b), math.hypot(c, d)
    det = affine.determinant(total)
    if su < _SCALE_EPS or sv < _SCALE_EPS or abs(det) < _SCALE_EPS:
        raise ValueError("singular transform")
    center = affine.apply(total, *_center(shape))
    angle = math.atan2(b, a)

    if isinstance(shape, TextShape):
        if det < 0:
            # A mirrored text would read backwards or upside down; keep the previous rotation instead.
            angle = math.radians(rotation_of(shape) or 0.0)
        size = max(1.0, shape.font_size * max(su, sv))
        return replace(shape, x=center[0], y=center[1], font_size=size, transform=_rotation_about(angle, center))

    if abs(a * c + b * d) > _ORTHO_EPS * su * sv:
        return replace(shape, transform=total)
    # Rects and ellipses look the same turned by 180°, so a flip folds into the rotation and the angle is
    # normalized to (-90°, 90°].
    if angle > math.pi / 2:
        angle -= math.pi
    elif angle <= -math.pi / 2:
        angle += math.pi
    rotation = _rotation_about(angle, center)
    if isinstance(shape, RectShape):
        w, h = max(shape.width * su, min_extent), max(shape.height * sv, min_extent)
        return replace(shape, x=center[0] - w / 2, y=center[1] - h / 2, width=w, height=h, transform=rotation)
    rx, ry = max(shape.rx * su, min_extent / 2), max(shape.ry * sv, min_extent / 2)
    return replace(shape, cx=center[0], cy=center[1], rx=rx, ry=ry, transform=rotation)


def rotation_of(shape: Shape) -> float | None:
    """Rotation in degrees (0 when untransformed), or None when the transform isn't a pure rotation."""
    if shape.transform == IDENTITY_TRANSFORM:
        return 0.0
    rotation = affine.as_rotation(shape.transform)
    return None if rotation is None else rotation[0]


def with_rotation(shape: RectShape | EllipseShape | TextShape, degrees: float) -> Shape:
    """Rotation about the shape's own center (anchor for text), replacing any previous rotation."""
    return replace(shape, transform=_rotation_about(math.radians(degrees), _center(shape)))


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
