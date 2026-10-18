"""Boolean path operations through skia-pathops (float32 inside; results are rounded)."""

import pathops

from veccy.geometry.boxes import Point
from veccy.geometry.segments import quad_to_cubic
from veccy.models.shapes import Close, CubicTo, LineTo, MoveTo, Segment

_BOOLEAN_OPS = {
    "union": pathops.PathOp.UNION,
    "difference": pathops.PathOp.DIFFERENCE,
}


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
