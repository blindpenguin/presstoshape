"""Model shapes as cached Skia paths, rebuilt only when the frozen shape changes."""

import math
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager

import skia

from presstoshape.geometry import transforms
from presstoshape.geometry.segments import quad_to_cubic
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    Gradient,
    GroupShape,
    ImageShape,
    LineTo,
    MoveTo,
    RectShape,
    Segment,
    Shape,
    Style,
    TextShape,
    Transform,
    content_children,
)
from presstoshape.render.gradients import gradient_shader
from presstoshape.render.images import ImageCache
from presstoshape.render.masks import build_clip
from presstoshape.render.text import text_path

_FILL_TYPES = {"nonzero": skia.PathFillType.kWinding, "evenodd": skia.PathFillType.kEvenOdd}
_CAPS = {"butt": skia.Paint.kButt_Cap, "round": skia.Paint.kRound_Cap, "square": skia.Paint.kSquare_Cap}
_JOINS = {"miter": skia.Paint.kMiter_Join, "round": skia.Paint.kRound_Join, "bevel": skia.Paint.kBevel_Join}


def to_skia_path(segments: tuple[Segment, ...], fill_rule: str = "nonzero") -> skia.Path:
    path = skia.Path()
    path.setFillType(_FILL_TYPES.get(fill_rule, skia.PathFillType.kWinding))
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


def from_skia_path(path: skia.Path) -> tuple[Segment, ...]:
    """Inverse of `to_skia_path`; quads and conics become cubics."""
    out: list[Segment] = []
    it = skia.Path.RawIter(path)
    while True:
        verb, pts = it.next()
        match verb:
            case skia.Path.kDone_Verb:
                return tuple(out)
            case skia.Path.kMove_Verb:
                out.append(MoveTo(pts[0].x(), pts[0].y()))
            case skia.Path.kLine_Verb:
                out.append(LineTo(pts[1].x(), pts[1].y()))
            case skia.Path.kQuad_Verb:
                out.append(quad_to_cubic(*((p.x(), p.y()) for p in pts)))
            case skia.Path.kConic_Verb:
                quads = skia.Path.ConvertConicToQuads(pts[0], pts[1], pts[2], it.conicWeight(), 2)
                for i in range(0, len(quads) - 2, 2):
                    out.append(quad_to_cubic(*((p.x(), p.y()) for p in quads[i : i + 3])))
            case skia.Path.kCubic_Verb:
                out.append(CubicTo(*(v for p in pts[1:] for v in (p.x(), p.y()))))
            case skia.Path.kClose_Verb:
                out.append(Close())


def to_skia_matrix(m: Transform) -> skia.Matrix:
    a, b, c, d, e, f = m
    return skia.Matrix.MakeAll(a, c, e, b, d, f, 0, 0, 1)


def stroke_paint(style: Style, width: float | None = None) -> skia.Paint:
    """The style's stroke geometry (width, cap, join, miter limit, dashes), no colour; `width` overrides the
    style's width (hit-testing widens thin strokes)."""
    paint = skia.Paint(
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=style.stroke_width if width is None else width,
        StrokeCap=_CAPS.get(style.cap, skia.Paint.kButt_Cap),
        StrokeJoin=_JOINS.get(style.join, skia.Paint.kMiter_Join),
        StrokeMiter=style.miter_limit,
        AntiAlias=True,
    )
    if style.dashes and sum(style.dashes) > 0:
        paint.setPathEffect(skia.DashPathEffect.Make(list(style.dashes), style.dash_offset))
    return paint


def _build(shape: Shape) -> skia.Path:
    """World-space geometry: the shape's transform is applied."""
    if isinstance(shape, TextShape):
        path = text_path(shape)
        if shape.transform != IDENTITY_TRANSFORM:
            path.transform(to_skia_matrix(shape.transform))
        return path
    fill_rule = "nonzero" if isinstance(shape, ImageShape) else shape.style.fill_rule
    return to_skia_path(transforms.outline(shape) or (), fill_rule)


def _bounds(shape: Shape, path: skia.Path) -> skia.Rect:
    rect = path.computeTightBounds()
    if isinstance(shape, ImageShape):
        return rect
    style = shape.style
    if style.stroke and style.stroke_width > 0:
        # Square caps reach past the end point diagonally; miter tips are left out, as before.
        half = style.stroke_width / 2 * (math.sqrt(2) if style.cap == "square" else 1.0)
        rect = rect.makeOutset(half, half)
    return rect


def _framed(children: Sequence[Shape]) -> Sequence[Shape]:
    """The children a container's bounds cover: the shown ones, or all when every one is hidden, so a
    container never collapses to an empty box."""
    shown = [child for child in children if not child.hidden]
    return shown or children


class PathCache:
    """Keyed by shape id; an entry is valid while its stored shape equals the current one."""

    def __init__(self) -> None:
        self.images = ImageCache()
        # Drawing context, set by `drawing` while a frame or a recording runs: the zoom the canvas matrix lacks
        # (pictures are recorded in document units) and whether reference images are drawn.
        self.zoom = 1.0
        self.references = True
        self._paths: dict[int, tuple[Shape, skia.Path, skia.Rect]] = {}
        self._strokes: dict[int, tuple[Shape, float, skia.Path]] = {}
        self._shaders: dict[int, tuple[Shape, tuple[skia.Shader | None, skia.Shader | None]]] = {}
        self._clips: dict[int, tuple[Shape, skia.Path]] = {}

    @contextmanager
    def drawing(self, zoom: float = 1.0, references: bool = True) -> Iterator[None]:
        before = self.zoom, self.references
        self.zoom, self.references = zoom, references
        try:
            yield
        finally:
            self.zoom, self.references = before

    def _entry(self, shape: Shape) -> tuple[Shape, skia.Path, skia.Rect]:
        entry = self._paths.get(shape.id)
        # Identity first: unchanged shapes are the same object, and equality on nested dataclasses is slow.
        if entry is None or (entry[0] is not shape and entry[0] != shape):
            if isinstance(shape, GroupShape):
                # Never drawn as one path; picked and framed through its children.
                entry = (shape, skia.Path(), self._group_bounds(shape, self.bounds))
                self._paths[shape.id] = entry
                return entry
            path = _build(shape)
            bounds = _bounds(shape, path)
            if isinstance(shape, CompositeShape) and path.isEmpty():
                bounds = self._union(self.bounds(part) for part in _framed(shape.parts))
            entry = (shape, path, bounds)
            self._paths[shape.id] = entry
        return entry

    def _group_bounds(self, group: GroupShape, child_bounds) -> skia.Rect:
        """What a group shows: its content, cut by the clip or the mask region. Mask objects don't count."""
        content = self._union(child_bounds(child) for child in _framed(content_children(group)))
        masking = group.masking
        if masking is None:
            return content
        visible = skia.Rect.MakeLTRB(content.left(), content.top(), content.right(), content.bottom())
        if masking.type == "clip":
            if masking.inverted:
                return content
            cut = self.clip(group).computeTightBounds()
        elif masking.region is not None:
            cut = skia.Rect.MakeXYWH(*masking.region)
        else:
            return content
        # A group clipped away entirely keeps its content's box, so it can still be found and selected.
        return visible if visible.intersect(cut) else content

    def clip(self, group: GroupShape) -> skia.Path:
        """The union of a masked group's mask objects, world space."""
        entry = self._clips.get(group.id)
        if entry is None or (entry[0] is not group and entry[0] != group):
            entry = (group, build_clip(group, self))
            self._clips[group.id] = entry
        return entry[1]

    @staticmethod
    def _union(rects) -> skia.Rect:
        result = skia.Rect.MakeEmpty()
        for rect in rects:
            result.join(rect)
        return result

    def get(self, shape: Shape) -> skia.Path:
        return self._entry(shape)[1]

    def stroke_path(self, shape: Shape, min_width: float = 0.0) -> skia.Path:
        """Filled outline of the shape's stroke, at least `min_width` wide (for hit-testing thin strokes)."""
        width = max(shape.style.stroke_width, min_width)
        entry = self._strokes.get(shape.id)
        if entry is None or (entry[0] is not shape and entry[0] != shape) or entry[1] != width:
            outline = skia.Path()
            stroke_paint(shape.style, width).getFillPath(self.get(shape), outline)
            entry = (shape, width, outline)
            self._strokes[shape.id] = entry
        return entry[2]

    def shaders(self, shape: Shape) -> tuple[skia.Shader | None, skia.Shader | None]:
        """Fill and stroke shaders of the shape's gradients (None for flat or missing paint). Built in the
        shape's own coordinates, where it is drawn."""
        entry = self._shaders.get(shape.id)
        if isinstance(shape, ImageShape):
            return None, None
        if entry is None or (entry[0] is not shape and entry[0] != shape):
            style = shape.style
            bounds = (
                self._local_bounds(shape)
                if isinstance(style.fill, Gradient) or isinstance(style.stroke, Gradient)
                else None
            )
            shaders = tuple(
                gradient_shader(paint, bounds) if isinstance(paint, Gradient) else None
                for paint in (style.fill, style.stroke)
            )
            entry = (shape, shaders)
            self._shaders[shape.id] = entry
        return entry[1]

    def _local_bounds(self, shape: Shape) -> skia.Rect:
        """Geometry box before the shape's transform. Paths and Composites keep an identity transform."""
        match shape:
            case RectShape(x=x, y=y, width=w, height=h):
                return skia.Rect.MakeXYWH(x, y, w, h)
            case EllipseShape(cx=cx, cy=cy, rx=rx, ry=ry):
                return skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry)
            case TextShape():
                return text_path(shape).computeTightBounds()
            case _:
                return self.get(shape).computeTightBounds()

    def bounds(self, shape: Shape) -> skia.Rect:
        """Geometry bounds grown by half the stroke width when stroked (like Qt's item boundingRect)."""
        return self._entry(shape)[2]

    def geometry_bounds(self, shape: Shape) -> skia.Rect:
        """Tight bounds of the transformed geometry, without stroke. An empty Composite uses its parts' bounds,
        so it can still be found, selected and framed; a group its children's."""
        if isinstance(shape, GroupShape):
            return self._group_bounds(shape, self.geometry_bounds)
        path = self.get(shape)
        if isinstance(shape, CompositeShape) and path.isEmpty():
            return self._union(self.geometry_bounds(part) for part in _framed(shape.parts))
        return path.computeTightBounds()

    def prune(self, live_ids: Iterable[int]) -> None:
        live = set(live_ids)
        for cache in (self._paths, self._strokes, self._shaders, self._clips):
            for shape_id in [i for i in cache if i not in live]:
                del cache[shape_id]
