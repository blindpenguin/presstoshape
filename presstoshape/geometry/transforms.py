"""Shape outlines and affine transforms on shapes, kept in canonical form (see transform_shape)."""

import math
from dataclasses import replace

import pathops

from presstoshape.geometry import affine, booleans, corners
from presstoshape.geometry.affine import Affine
from presstoshape.geometry.aspect import visible_box
from presstoshape.geometry.boxes import Point
from presstoshape.geometry.segments import ellipse_segments, rect_segments, transform_segments
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    Aspect,
    CompositeShape,
    EllipseShape,
    GroupShape,
    ImageShape,
    Masking,
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
    """Shape geometry as path segments with its transform applied, or None for text and groups (no single vector
    outline).

    A Composite's outline is its parts combined by their modes; degenerate parts that pathops can't handle give
    an empty outline rather than an error, so one bad part can't break drawing.
    """
    match shape:
        case CompositeShape():
            return _composite_outline(shape)
        case RectShape(x=x, y=y, width=w, height=h, rx=rx, ry=ry):
            segments = rect_segments(x, y, w, h, rx, ry)
        case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
            segments = ellipse_segments(cx, cy, rx, ry)
        case PathShape(segments=segments):
            segments = corners.rounded(segments)
        case ImageShape():
            segments = rect_segments(*visible_box(shape), 0.0, 0.0)
        case TextShape() | GroupShape():
            return None
    return _apply_affine(segments, shape.transform)


def area_outline(shape: Shape) -> tuple[Segment, ...] | None:
    """`outline` as the area the shape fills, safe for booleans: an even-odd shape is rewritten so its holes
    survive the nonzero rule the boolean code assumes. Not for drawing: strokes follow the original contours.
    Raises pathops.PathOpsError when pathops can't simplify the outline."""
    segments = outline(shape)
    if segments is None or isinstance(shape, ImageShape) or shape.style.fill_rule != "evenodd":
        return segments
    return booleans.simplify(segments, evenodd=True)


def _composite_outline(composite: CompositeShape) -> tuple[Segment, ...]:
    try:
        parts = [
            (part_outline, mode)
            for part, mode in zip(composite.parts, composite.modes)
            if not part.hidden and (part_outline := area_outline(part)) is not None
        ]
        return booleans.combine_parts(parts)
    except pathops.PathOpsError:
        return ()


def _apply_affine(segments: tuple[Segment, ...], m: Affine) -> tuple[Segment, ...]:
    if m == IDENTITY_TRANSFORM:
        return segments
    return transform_segments(segments, lambda x, y: affine.apply(m, x, y))


def _masking_through(masking: Masking | None, m: Affine) -> Masking | None:
    """The mask region follows its group; under a rotation or skew it becomes the box around the turned region."""
    if masking is None or masking.region is None:
        return masking
    x, y, width, height = masking.region
    corners = [affine.apply(m, px, py) for px, py in ((x, y), (x + width, y), (x, y + height), (x + width, y + height))]
    left, right = min(c[0] for c in corners), max(c[0] for c in corners)
    top, bottom = min(c[1] for c in corners), max(c[1] for c in corners)
    return replace(masking, region=(left, top, right - left, bottom - top))


def translate(shape: Shape, dx: float, dy: float) -> Shape:
    match shape:
        case CompositeShape():
            return replace(shape, parts=tuple(translate(part, dx, dy) for part in shape.parts))
        case GroupShape():
            return replace(
                shape,
                children=tuple(translate(child, dx, dy) for child in shape.children),
                masking=_masking_through(shape.masking, (1.0, 0.0, 0.0, 1.0, dx, dy)),
            )
        case PathShape():
            return replace(shape, segments=transform_segments(shape.segments, lambda x, y: (x + dx, y + dy)))
        case RectShape() | TextShape() | ImageShape():
            moved = replace(shape, x=shape.x + dx, y=shape.y + dy)
        case EllipseShape():
            moved = replace(shape, cx=shape.cx + dx, cy=shape.cy + dy)
    if shape.transform == IDENTITY_TRANSFORM:
        return moved
    # Conjugate so the transform keeps acting about the moved geometry (rotation stays about the new center).
    shift = affine.translation(dx, dy)
    return replace(moved, transform=affine.compose(shift, affine.compose(shape.transform, affine.invert(shift))))


def _center(shape: RectShape | EllipseShape | TextShape | ImageShape) -> Point:
    match shape:
        case RectShape(x=x, y=y, width=w, height=h) | ImageShape(x=x, y=y, width=w, height=h):
            return x + w / 2, y + h / 2
        case EllipseShape(cx=cx, cy=cy):
            return cx, cy
        case TextShape(x=x, y=y):
            return x, y


def _rotation_about(radians: float, center: Point) -> Affine:
    if abs(math.remainder(radians, math.tau)) < _ANGLE_EPS:
        return IDENTITY_TRANSFORM
    return affine.rotation(radians, *center)


def transform_shape(shape: Shape, m: Affine, min_extent: float = 0.0, scale_radii: bool = False) -> Shape:
    """`shape` with `m` applied on top of its transform, in canonical form.

    Paths get the transform baked into their segments. Rect/ellipse keep axis scales in their size and only a
    rotation about their center in `transform`, unless the result is skewed (then the full matrix is kept). Text
    scales uniformly by the larger axis factor and keeps its rotation about the anchor. Rect corner radii stay
    as they are (resizing keeps the rounding) unless `scale_radii`, which scales them with the axes like SVG
    import needs. Raises ValueError when the result would be singular.
    """
    if isinstance(shape, CompositeShape):
        return replace(shape, parts=tuple(transform_shape(part, m, min_extent, scale_radii) for part in shape.parts))
    if isinstance(shape, GroupShape):
        children = tuple(transform_shape(child, m, min_extent, scale_radii) for child in shape.children)
        return replace(shape, children=children, masking=_masking_through(shape.masking, m))
    total = affine.compose(m, shape.transform)
    if isinstance(shape, PathShape):
        return replace(shape, segments=_apply_affine(shape.segments, total), transform=IDENTITY_TRANSFORM)
    a, b, c, d = total[:4]
    su, sv = math.hypot(a, b), math.hypot(c, d)
    det = affine.determinant(total)
    if su < _SCALE_EPS or sv < _SCALE_EPS or abs(det) < _SCALE_EPS:
        raise ValueError("singular transform")
    if isinstance(shape, ImageShape) and shape.aspect.align != "none" and abs(su - sv) > _ORTHO_EPS * max(su, sv):
        # Stretching a picture that is fitted into its box: a sliced one keeps the matrix (the clip must follow),
        # a letterboxed one becomes its drawn area with `none`, so the stretch shows as such.
        if shape.aspect.slice:
            return replace(shape, transform=total)
        left, top, width, height = visible_box(shape)
        shape = replace(shape, x=left, y=top, width=width, height=height, aspect=Aspect("none"))
    center = affine.apply(total, *_center(shape))
    angle = math.atan2(b, a)

    if isinstance(shape, TextShape):
        if det < 0:
            # A mirrored text would read backwards or upside down; keep the previous rotation instead.
            angle = math.radians(rotation_of(shape) or 0.0)
        size = max(1.0, shape.font_size * max(su, sv))
        return replace(shape, x=center[0], y=center[1], font_size=size, transform=_rotation_about(angle, center))

    # A picture is not mirror-symmetric like a rect, so a flip stays in the matrix.
    if abs(a * c + b * d) > _ORTHO_EPS * su * sv or (det < 0 and isinstance(shape, ImageShape)):
        return replace(shape, transform=total)
    # Rects and ellipses look the same turned by 180°, so a flip folds into the rotation and the angle is
    # normalized to (-90°, 90°].
    if angle > math.pi / 2:
        angle -= math.pi
    elif angle <= -math.pi / 2:
        angle += math.pi
    rotation = _rotation_about(angle, center)
    if isinstance(shape, (RectShape, ImageShape)):
        w, h = max(shape.width * su, min_extent), max(shape.height * sv, min_extent)
        radii = {"rx": shape.rx * su, "ry": shape.ry * sv} if scale_radii and isinstance(shape, RectShape) else {}
        return replace(shape, x=center[0] - w / 2, y=center[1] - h / 2, width=w, height=h, transform=rotation, **radii)
    rx, ry = max(shape.rx * su, min_extent / 2), max(shape.ry * sv, min_extent / 2)
    return replace(shape, cx=center[0], cy=center[1], rx=rx, ry=ry, transform=rotation)


def rotation_of(shape: Shape) -> float | None:
    """Rotation in degrees (0 when untransformed), or None when the transform isn't a pure rotation."""
    if shape.transform == IDENTITY_TRANSFORM:
        return 0.0
    rotation = affine.as_rotation(shape.transform)
    return None if rotation is None else rotation[0]


def with_rotation(shape: RectShape | EllipseShape | TextShape | ImageShape, degrees: float) -> Shape:
    """Rotation about the shape's own center (anchor for text), replacing any previous rotation."""
    return replace(shape, transform=_rotation_about(math.radians(degrees), _center(shape)))
