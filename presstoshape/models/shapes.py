"""Immutable shape/geometry data. Frozen so undo snapshots can share shapes and views can diff by equality."""

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import Literal, get_args


@dataclass(frozen=True)
class MoveTo:
    x: float
    y: float
    # A corner node keeps its handles independent (no smooth mirroring), even when they happen to line up.
    corner: bool = False


@dataclass(frozen=True)
class LineTo:
    x: float
    y: float
    corner: bool = False


@dataclass(frozen=True)
class CubicTo:
    c1x: float
    c1y: float
    c2x: float
    c2y: float
    x: float
    y: float
    corner: bool = False


@dataclass(frozen=True)
class Close:
    pass


Segment = MoveTo | LineTo | CubicTo | Close

# Affine (a, b, c, d, e, f) as in SVG matrix(); applied on top of the shape's geometry.
Transform = tuple[float, float, float, float, float, float]
IDENTITY_TRANSFORM: Transform = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


FillRule = Literal["nonzero", "evenodd"]
GradientUnits = Literal["objectBoundingBox", "userSpaceOnUse"]
SpreadMethod = Literal["pad", "reflect", "repeat"]
LineCap = Literal["butt", "round", "square"]
LineJoin = Literal["miter", "round", "bevel"]
TextAnchor = Literal["start", "middle", "end"]


MAX_STOPS = 1024


@dataclass(frozen=True)
class GradientStop:
    offset: float
    color: str
    opacity: float = 1.0


@dataclass(frozen=True)
class LinearGradient:
    """Coordinates are fractions of the shape's bounding box for `objectBoundingBox`, user-space numbers
    (in the shape's own coordinate system) for `userSpaceOnUse`."""

    x1: float
    y1: float
    x2: float
    y2: float
    stops: tuple[GradientStop, ...]
    units: GradientUnits = "objectBoundingBox"
    spread: SpreadMethod = "pad"
    transform: Transform = IDENTITY_TRANSFORM


@dataclass(frozen=True)
class RadialGradient:
    cx: float
    cy: float
    r: float
    fx: float
    fy: float
    stops: tuple[GradientStop, ...]
    units: GradientUnits = "objectBoundingBox"
    spread: SpreadMethod = "pad"
    transform: Transform = IDENTITY_TRANSFORM


Gradient = LinearGradient | RadialGradient
# A colour (#rrggbb), a gradient, or None for no paint.
Paint = str | Gradient | None


def flat_color(paint: Paint) -> str | None:
    """The one colour that stands for `paint`: the colour itself, a gradient's first stop, None for no paint."""
    if isinstance(paint, (LinearGradient, RadialGradient)):
        return paint.stops[0].color if paint.stops else None
    return paint


@dataclass(frozen=True)
class Style:
    """Paint of a shape. Defaults match SVG, so a style without the newer fields draws as SVG would."""

    fill: Paint = "#3b82f6"
    stroke: Paint = "#18181b"
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


def _finite(value: float, default: float) -> float:
    return float(value) if math.isfinite(value) else default


def _stops(stops: tuple[GradientStop, ...]) -> tuple[GradientStop, ...]:
    result: list[GradientStop] = []
    previous = 0.0
    for stop in tuple(stops)[:MAX_STOPS]:
        offset = min(1.0, max(previous, _finite(stop.offset, previous)))
        previous = offset
        result.append(GradientStop(offset, stop.color, _unit(stop.opacity)))
    return tuple(result)


def _invertible(m: Transform) -> bool:
    return all(math.isfinite(v) for v in m) and abs(m[0] * m[3] - m[1] * m[2]) > 1e-12


@lru_cache(maxsize=512)
def _sanitized_gradient(paint: Gradient) -> Gradient | None:
    stops = _stops(paint.stops)
    if not stops:
        return None
    common = {
        "stops": stops,
        "units": paint.units if paint.units in get_args(GradientUnits) else "objectBoundingBox",
        "spread": paint.spread if paint.spread in get_args(SpreadMethod) else "pad",
        "transform": paint.transform if _invertible(paint.transform) else IDENTITY_TRANSFORM,
    }
    if isinstance(paint, LinearGradient):
        x1, y1, x2, y2 = (
            _finite(v, d) for v, d in ((paint.x1, 0.0), (paint.y1, 0.0), (paint.x2, 1.0), (paint.y2, 0.0))
        )
        return LinearGradient(x1, y1, x2, y2, **common)
    if not math.isfinite(paint.r) or paint.r < 0:
        return None
    cx, cy = _finite(paint.cx, 0.5), _finite(paint.cy, 0.5)
    fx, fy = _finite(paint.fx, cx), _finite(paint.fy, cy)
    distance = math.hypot(fx - cx, fy - cy)
    if distance > paint.r:
        fx, fy = (cx + (fx - cx) * paint.r / distance, cy + (fy - cy) * paint.r / distance)
    return RadialGradient(cx, cy, float(paint.r), fx, fy, **common)


def _sanitized_paint(paint: Paint) -> Paint:
    if isinstance(paint, (LinearGradient, RadialGradient)):
        clean = _sanitized_gradient(paint)
        # An unchanged gradient stays the very object it was, so shapes that share one keep sharing it.
        return paint if clean == paint else clean
    return paint


def sanitized(style: Style) -> Style:
    """`style` with every field in range: opacities clamped, unknown enum values reset, dashes normalized."""
    defaults = Style()
    return replace(
        style,
        fill=_sanitized_paint(style.fill),
        stroke=_sanitized_paint(style.stroke),
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
class Aspect:
    # "none" or one of xMinYMin … xMaxYMax.
    align: str
    slice: bool = False


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
    hidden: bool = False
    locked: bool = False


@dataclass(frozen=True)
class EllipseShape:
    id: int
    cx: float
    cy: float
    rx: float
    ry: float
    style: Style
    transform: Transform = IDENTITY_TRANSFORM
    hidden: bool = False
    locked: bool = False


@dataclass(frozen=True)
class PathShape:
    id: int
    segments: tuple[Segment, ...]
    style: Style
    transform: Transform = IDENTITY_TRANSFORM
    hidden: bool = False
    locked: bool = False


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
    hidden: bool = False
    locked: bool = False


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
    hidden: bool = False
    locked: bool = False


MaskType = Literal["clip", "luminance", "alpha"]


@dataclass(frozen=True)
class Masking:
    """What turns a group into a clipping or opacity mask: the children listed in `mask_ids` are the mask objects,
    all other children the content. `region` (x, y, width, height in the group's space) is the SVG mask
    rectangle for opacity masks; None cuts nothing."""

    type: MaskType
    mask_ids: tuple[int, ...]
    inverted: bool = False
    region: tuple[float, float, float, float] | None = None

    def is_mask(self, shape_id: int) -> bool:
        return shape_id in self.mask_ids


@dataclass(frozen=True)
class GroupShape:
    """Shapes kept together as one object; each child keeps its own style. Drawn as its children, composited
    together with `opacity` when that is below 1. Has no paint of its own. With `masking`, the content is clipped
    or masked by the mask objects among the children."""

    id: int
    children: tuple["Shape", ...]
    opacity: float = 1.0
    # Stays identity: transforms are applied to the children.
    transform: Transform = IDENTITY_TRANSFORM
    hidden: bool = False
    locked: bool = False
    masking: Masking | None = None


@dataclass(frozen=True)
class ImageData:
    """An encoded image file, shared by every shape that shows it. Identity is the digest (lowercase hex SHA-256
    of `data`); `width` and `height` are the displayed pixel size, EXIF orientation applied."""

    data: bytes = field(repr=False, compare=False)
    width: int
    height: int
    mime: str
    digest: str


IMAGE_ALIGNS = frozenset(f"x{x}Y{y}" for x in ("Min", "Mid", "Max") for y in ("Min", "Mid", "Max")) | {"none"}
_DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class ImageShape:
    """A picture in the viewport rectangle (x, y, width, height) as SVG `<image>`: `aspect` decides how it fits.
    A reference image is dimmed, locked and never exported."""

    id: int
    x: float
    y: float
    width: float
    height: float
    data: ImageData
    aspect: Aspect = Aspect("xMidYMid")
    opacity: float = 1.0
    transform: Transform = IDENTITY_TRANSFORM
    reference: bool = False
    hidden: bool = False
    locked: bool = False


def sanitized_image(shape: ImageShape) -> ImageShape:
    """`shape` with a finite, non-negative size and position, opacity in 0..1 and a known alignment."""

    def finite(value: float, fallback: float = 0.0) -> float:
        return value if math.isfinite(value) else fallback

    aspect = shape.aspect if shape.aspect.align in IMAGE_ALIGNS else Aspect("xMidYMid")
    return replace(
        shape,
        x=finite(shape.x),
        y=finite(shape.y),
        width=max(0.0, finite(shape.width)),
        height=max(0.0, finite(shape.height)),
        opacity=_unit(shape.opacity),
        aspect=Aspect(aspect.align, bool(aspect.slice) and aspect.align != "none"),
    )


def valid_digest(digest: str) -> bool:
    return _DIGEST.fullmatch(digest) is not None


Shape = RectShape | EllipseShape | PathShape | TextShape | CompositeShape | GroupShape | ImageShape
# Shapes that can be entered to work on the shapes inside them.
ContainerShape = CompositeShape | GroupShape


def children_of(shape: "Shape") -> tuple["Shape", ...]:
    """A Composite's parts or a group's children; () for other shapes."""
    if isinstance(shape, CompositeShape):
        return shape.parts
    if isinstance(shape, GroupShape):
        return shape.children
    return ()


def mask_children(group: GroupShape) -> tuple[Shape, ...]:
    masking = group.masking
    return tuple(child for child in group.children if masking is not None and masking.is_mask(child.id))


def content_children(group: GroupShape) -> tuple[Shape, ...]:
    masking = group.masking
    return tuple(child for child in group.children if masking is None or not masking.is_mask(child.id))


def sanitized_masking(masking: Masking, child_ids: Iterable[int]) -> Masking:
    """`masking` with an unknown type reset to a clip, `mask_ids` cut down to existing children (once each, in
    child order) and an unusable region dropped."""
    existing = set(child_ids)
    seen: set[int] = set()
    mask_ids = tuple(i for i in masking.mask_ids if i in existing and not (i in seen or seen.add(i)))
    region = masking.region
    if region is not None:
        region = tuple(region)
        if len(region) != 4 or not all(math.isfinite(v) for v in region) or region[2] < 0 or region[3] < 0:
            region = None
        else:
            region = tuple(float(v) for v in region)
    return Masking(
        masking.type if masking.type in get_args(MaskType) else "clip",
        mask_ids,
        bool(masking.inverted),
        region,
    )
