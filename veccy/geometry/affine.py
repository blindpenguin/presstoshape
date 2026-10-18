"""2D affine transforms as plain tuples in SVG `matrix(a b c d e f)` order: x' = a*x + c*y + e, y' = b*x + d*y + f."""

import math

from veccy.geometry.boxes import Point

Affine = tuple[float, float, float, float, float, float]

IDENTITY: Affine = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_EPS = 1e-9


def compose(outer: Affine, inner: Affine) -> Affine:
    """Matrix applying `inner` first, then `outer`."""
    a1, b1, c1, d1, e1, f1 = outer
    a2, b2, c2, d2, e2, f2 = inner
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def apply(m: Affine, x: float, y: float) -> Point:
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def determinant(m: Affine) -> float:
    return m[0] * m[3] - m[1] * m[2]


def invert(m: Affine) -> Affine:
    a, b, c, d, e, f = m
    det = determinant(m)
    if abs(det) < _EPS:
        raise ValueError("singular transform")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f))


def translation(dx: float, dy: float) -> Affine:
    return (1.0, 0.0, 0.0, 1.0, dx, dy)


def rotation(radians: float, cx: float = 0.0, cy: float = 0.0) -> Affine:
    cos, sin = math.cos(radians), math.sin(radians)
    return (cos, sin, -sin, cos, cx - cos * cx + sin * cy, cy - sin * cx - cos * cy)


def scaling(sx: float, sy: float, cx: float = 0.0, cy: float = 0.0) -> Affine:
    return (sx, 0.0, 0.0, sy, cx - sx * cx, cy - sy * cy)


def is_identity(m: Affine, eps: float = _EPS) -> bool:
    return all(abs(v - i) <= eps for v, i in zip(m, IDENTITY))


def as_rotation(m: Affine, eps: float = _EPS) -> tuple[float, float, float] | None:
    """(degrees, cx, cy) when `m` is a pure rotation about some point, else None. Identity gives (0, 0, 0)."""
    a, b, c, d, e, f = m
    if abs(a - d) > eps or abs(b + c) > eps or abs(a * a + b * b - 1) > eps:
        return None
    if abs(b) <= eps and a > 0:
        return (0.0, 0.0, 0.0) if abs(e) <= eps and abs(f) <= eps else None
    # Fixed point of the rotation: solve (I - R) c = t.
    p, q = 1 - a, b
    det = p * p + q * q
    cx = (p * e - q * f) / det
    cy = (q * e + p * f) / det
    return math.degrees(math.atan2(b, a)), cx, cy
