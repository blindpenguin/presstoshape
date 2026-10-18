"""Shape outlines and affine transforms on shapes, kept in canonical form (see transform_shape)."""

import math
from dataclasses import replace

from presstoshape.geometry import affine
from presstoshape.geometry.affine import Affine
from presstoshape.geometry.boxes import Point
from presstoshape.geometry.segments import ellipse_segments, rect_segments, transform_segments
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    EllipseShape,
    PathShape,
    RectShape,
    Segment,
    Shape,
    TextShape,
)

_ANGLE_EPS = 1e-9
_SCALE_EPS = 1e-12
_ORTHO_EPS = 1e-9


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
