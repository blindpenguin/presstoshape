"""Boolean path operations through skia-pathops (float32 inside; results are rounded)."""

from collections.abc import Sequence

import pathops

from presstoshape.geometry.boxes import Point
from presstoshape.geometry.segments import quad_to_cubic
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, PartMode, Segment

Segments = tuple[Segment, ...]
# How a part combines with everything below it.
Mode = PartMode

_PATHOPS: dict[str, pathops.PathOp] = {
    "add": pathops.PathOp.UNION,
    "subtract": pathops.PathOp.DIFFERENCE,
    "intersect": pathops.PathOp.INTERSECTION,
    "exclude": pathops.PathOp.XOR,
}


def combine_parts(parts: Sequence[tuple[Segments, Mode]]) -> Segments:
    """Combines parts bottom to top: the first part is the starting area whatever its mode, and every
    following part is applied to everything below it with its own mode."""
    if not parts:
        return ()
    (first, _), *rest = parts
    result = _to_skia(first)
    for outline, mode in rest:
        result = pathops.op(result, _to_skia(outline), _PATHOPS[mode])
    return _from_skia(result)


def simplify(segments: Segments, evenodd: bool) -> Segments:
    """The same filled area with no overlapping or wrongly wound contours, so it fills the same under the
    nonzero rule as `segments` did under its own rule."""
    path = _to_skia(segments, evenodd)
    path.simplify()
    return _from_skia(path)


def area(segments: Segments) -> float:
    return abs(_to_skia(segments).area)


def mismatch_area(first: Segments, second: Segments) -> float:
    """Area covered by exactly one of two outlines: 0 when they describe the same shape, however written."""
    return abs(pathops.op(_to_skia(first), _to_skia(second), pathops.PathOp.XOR).area)


# Pieces smaller than this (square doc units) are float32 slivers along shared edges, not real areas.
MIN_PIECE_AREA = 1e-3


def split_regions(segments: Segments) -> list[Segments]:
    """Connected areas of an outline, each with the holes inside it."""
    return [_from_skia(region) for region in _regions(_to_skia(segments))]


def divide(outlines: Sequence[Segments]) -> list[tuple[Segments, int]]:
    """Every area covered by a different set of outlines, split into connected regions.

    Each piece is tagged with the index of the top-most outline covering it. Built one outline at a time:
    existing pieces split into the part inside and outside the new outline, and the new outline's uncovered
    rest becomes a piece of its own.
    """
    pieces: list[tuple[pathops.Path, int]] = []
    covered = pathops.Path()
    for index, outline in enumerate(outlines):
        shape = _to_skia(outline)
        next_pieces: list[tuple[pathops.Path, int]] = []
        for piece, top in pieces:
            inside = pathops.op(piece, shape, pathops.PathOp.INTERSECTION)
            outside = pathops.op(piece, shape, pathops.PathOp.DIFFERENCE)
            next_pieces += [(part, owner) for part, owner in ((inside, index), (outside, top)) if _has_area(part)]
        rest = pathops.op(shape, covered, pathops.PathOp.DIFFERENCE)
        if _has_area(rest):
            next_pieces.append((rest, index))
        covered = pathops.op(covered, shape, pathops.PathOp.UNION)
        pieces = next_pieces
    return [
        (_from_skia(region), top)
        for piece, top in pieces
        for region in _regions(piece)
        if abs(region.area) >= MIN_PIECE_AREA
    ]


def _has_area(path: pathops.Path) -> bool:
    return abs(path.area) >= MIN_PIECE_AREA


def _regions(path: pathops.Path) -> list[pathops.Path]:
    """After simplifying, a contour inside an even number of other contours is an outer boundary, inside an odd
    number it's a hole; a hole belongs to the smallest outer boundary one level up that contains it."""
    path.simplify()
    contours = list(path.contours)
    if len(contours) <= 1:
        return [path] if contours else []
    anchors = [contour.firstPoints[0] for contour in contours]
    depth = [
        sum(other.contains(anchors[index]) for other_index, other in enumerate(contours) if other_index != index)
        for index in range(len(contours))
    ]
    regions: dict[int, pathops.Path] = {}
    for index, contour in enumerate(contours):
        if depth[index] % 2 == 0:
            region = pathops.Path()
            region.addPath(contour)
            regions[index] = region
    for index, contour in enumerate(contours):
        if depth[index] % 2 == 0:
            continue
        owners = [
            outer for outer in regions if depth[outer] == depth[index] - 1 and contours[outer].contains(anchors[index])
        ]
        if owners:
            regions[min(owners, key=lambda outer: abs(contours[outer].area))].addPath(contour)
    return [region for _, region in sorted(regions.items())]


def _to_skia(segments: tuple[Segment, ...], evenodd: bool = False) -> pathops.Path:
    path = pathops.Path(fillType=pathops.FillType.EVEN_ODD if evenodd else pathops.FillType.WINDING)
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
