"""Turning a freehand stroke into a few smooth cubic beziers.

Four steps: drop samples closer than a screen pixel, split at corners (sharp turns), smooth each run lightly
(corners and ends stay put), then fit each run with Philip J. Schneider's algorithm ("An Algorithm for
Automatically Fitting Digitized Curves", Graphics Gems, 1990): least squares for the inner control points,
Newton-Raphson reparameterization, and splitting at the worst point with a shared tangent until the error is
within tolerance. All distances are in screen pixels at the zoom used while drawing (`pixel_size` converts).
"""

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass

from presstoshape.geometry.boxes import Point
from presstoshape.models.shapes import Close, CubicTo, MoveTo, Segment

_DECIMATE_PX = 1.0
_MIN_LENGTH_PX = 3.0
_CORNER_ANGLE = math.radians(70)
_CORNER_REACH_PX = 8.0
_MAX_PRESMOOTH = 4
_MAX_TOLERANCE_PX = 12.0
_REPARAMETERIZE_STEPS = 4
_MAX_DEPTH = 32
# A fitted handle longer than this many chords is a numerical accident; fall back to chord / 3.
_MAX_HANDLE_CHORDS = 3.0

Bezier = tuple[Point, Point, Point, Point]


@dataclass(frozen=True)
class StrokeSample:
    x: float
    y: float
    # Recorded for pressure-sensitive strokes later; the fitting only uses positions.
    pressure: float = 1.0
    time: float = 0.0


# --- small vector helpers --------------------------------------------------------------------------


def _sub(a: Point, b: Point) -> Point:
    return a[0] - b[0], a[1] - b[1]


def _add(a: Point, b: Point) -> Point:
    return a[0] + b[0], a[1] + b[1]


def _scale(a: Point, factor: float) -> Point:
    return a[0] * factor, a[1] * factor


def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _unit(vector: Point) -> Point:
    length = math.hypot(*vector)
    return (vector[0] / length, vector[1] / length) if length > 1e-12 else (0.0, 0.0)


# --- preparing the points ---------------------------------------------------------------------------


def _decimate(points: list[Point], spacing: float) -> list[Point]:
    kept = [points[0]]
    for point in points[1:]:
        if _distance(point, kept[-1]) >= spacing:
            kept.append(point)
    if len(kept) > 1 and kept[-1] != points[-1]:
        kept[-1] = points[-1]
    return kept


def _length(points: list[Point]) -> float:
    return sum(_distance(a, b) for a, b in zip(points, points[1:]))


def _arc_lengths(points: list[Point]) -> list[float]:
    lengths = [0.0]
    for a, b in zip(points, points[1:]):
        lengths.append(lengths[-1] + _distance(a, b))
    return lengths


def _turns(points: list[Point], reach: float, cyclic: bool) -> list[float]:
    """Turning angle at every point, measured to the points `reach` away along the stroke (0 where the stroke
    doesn't reach that far). Arc length instead of straight distance keeps it linear in the number of points."""
    if cyclic:
        # Walk around the loop: the points on either side wrap past the seam.
        wrapped = points[-len(points) // 2 :] + points + points[: len(points) // 2]
        offset = len(points) // 2
    else:
        wrapped, offset = points, 0
    lengths = _arc_lengths(wrapped)
    turns = []
    for index in range(offset, offset + len(points)):
        before = bisect.bisect_right(lengths, lengths[index] - reach) - 1
        after = bisect.bisect_left(lengths, lengths[index] + reach)
        if before < 0 or after >= len(wrapped):
            turns.append(0.0)
            continue
        incoming = _unit(_sub(wrapped[index], wrapped[before]))
        outgoing = _unit(_sub(wrapped[after], wrapped[index]))
        turns.append(math.acos(max(-1.0, min(1.0, _dot(incoming, outgoing)))))
    return turns


def _corners(points: list[Point], reach: float, cyclic: bool) -> list[int]:
    """Indices where the stroke turns sharply; of the candidates within `reach` of each other along the stroke,
    only the sharpest counts."""
    turns = _turns(points, reach, cyclic)
    lengths = _arc_lengths(points)
    candidates = [index for index, turn in enumerate(turns) if turn >= _CORNER_ANGLE]
    if not cyclic:
        candidates = [index for index in candidates if 0 < index < len(points) - 1]
    corners: list[int] = []
    group: list[int] = []
    for index in candidates:
        if group and lengths[index] - lengths[group[-1]] > reach:
            corners.append(max(group, key=lambda member: turns[member]))
            group = []
        group.append(index)
    if group:
        corners.append(max(group, key=lambda member: turns[member]))
    return corners


def _presmooth(run: list[Point], window: int) -> list[Point]:
    """Moving average over ±window points; the run's ends stay fixed."""
    if window == 0 or len(run) < 3:
        return run
    smoothed = [run[0]]
    for index in range(1, len(run) - 1):
        low, high = max(0, index - window), min(len(run) - 1, index + window)
        span = run[low : high + 1]
        smoothed.append((sum(p[0] for p in span) / len(span), sum(p[1] for p in span) / len(span)))
    smoothed.append(run[-1])
    return smoothed


# --- Schneider's fit -----------------------------------------------------------------------------------


def _bezier_point(bezier: Bezier, t: float) -> Point:
    mt = 1 - t
    a, b, c, d = mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t
    return (
        a * bezier[0][0] + b * bezier[1][0] + c * bezier[2][0] + d * bezier[3][0],
        a * bezier[0][1] + b * bezier[1][1] + c * bezier[2][1] + d * bezier[3][1],
    )


def _chord_parameters(points: list[Point]) -> list[float]:
    distances = [0.0]
    for a, b in zip(points, points[1:]):
        distances.append(distances[-1] + _distance(a, b))
    total = distances[-1] or 1.0
    return [distance / total for distance in distances]


def _handles(start: Point, end: Point, left_tangent: Point, right_tangent: Point, length: float) -> Bezier:
    return start, _add(start, _scale(left_tangent, length)), _add(end, _scale(right_tangent, length)), end


def _generate(points: list[Point], parameters: list[float], left_tangent: Point, right_tangent: Point) -> Bezier:
    """Least-squares inner control points along the given end tangents."""
    start, end = points[0], points[-1]
    c00 = c01 = c11 = x0 = x1 = 0.0
    for point, t in zip(points, parameters):
        mt = 1 - t
        b0, b1, b2, b3 = mt * mt * mt, 3 * mt * mt * t, 3 * mt * t * t, t * t * t
        a1, a2 = _scale(left_tangent, b1), _scale(right_tangent, b2)
        c00 += _dot(a1, a1)
        c01 += _dot(a1, a2)
        c11 += _dot(a2, a2)
        rest = _sub(point, _add(_scale(start, b0 + b1), _scale(end, b2 + b3)))
        x0 += _dot(a1, rest)
        x1 += _dot(a2, rest)
    determinant = c00 * c11 - c01 * c01
    chord = _distance(start, end)
    if abs(determinant) > 1e-12:
        alpha_left = (x0 * c11 - c01 * x1) / determinant
        alpha_right = (c00 * x1 - c01 * x0) / determinant
    else:
        alpha_left = alpha_right = 0.0
    limit = _MAX_HANDLE_CHORDS * chord
    epsilon = 1e-6 * chord
    if not (epsilon < alpha_left < limit and epsilon < alpha_right < limit):
        # Wu-Barsky heuristic: handles a third of the chord along the tangents.
        alpha_left = alpha_right = chord / 3
    return (
        start,
        _add(start, _scale(left_tangent, alpha_left)),
        _add(end, _scale(right_tangent, alpha_right)),
        end,
    )


def _max_error(points: list[Point], bezier: Bezier, parameters: list[float]) -> tuple[float, int]:
    worst, split = 0.0, len(points) // 2
    for index in range(1, len(points) - 1):
        error = _distance(_bezier_point(bezier, parameters[index]), points[index]) ** 2
        if error >= worst:
            worst, split = error, index
    return worst, split


def _newton(bezier: Bezier, point: Point, t: float) -> float:
    """One Newton-Raphson step towards the parameter of the curve point closest to `point`."""
    p0, p1, p2, p3 = bezier
    q = _bezier_point(bezier, t)
    mt = 1 - t
    d1 = [_scale(_sub(p1, p0), 3), _scale(_sub(p2, p1), 3), _scale(_sub(p3, p2), 3)]
    d2 = [_scale(_sub(d1[1], d1[0]), 2), _scale(_sub(d1[2], d1[1]), 2)]
    q1 = _add(_add(_scale(d1[0], mt * mt), _scale(d1[1], 2 * mt * t)), _scale(d1[2], t * t))
    q2 = _add(_scale(d2[0], mt), _scale(d2[1], t))
    difference = _sub(q, point)
    numerator = _dot(difference, q1)
    denominator = _dot(q1, q1) + _dot(difference, q2)
    if abs(denominator) < 1e-12:
        return t
    return min(1.0, max(0.0, t - numerator / denominator))


def _fit(points: list[Point], left_tangent: Point, right_tangent: Point, tolerance: float, depth: int) -> list[Bezier]:
    start, end = points[0], points[-1]
    if len(points) == 2 or depth >= _MAX_DEPTH:
        return [_handles(start, end, left_tangent, right_tangent, _distance(start, end) / 3)]
    parameters = _chord_parameters(points)
    bezier = _generate(points, parameters, left_tangent, right_tangent)
    error, split = _max_error(points, bezier, parameters)
    squared_tolerance = tolerance * tolerance
    if error <= squared_tolerance:
        return [bezier]
    if error <= squared_tolerance * 16:
        for _ in range(_REPARAMETERIZE_STEPS):
            parameters = [_newton(bezier, point, t) for point, t in zip(points, parameters)]
            bezier = _generate(points, parameters, left_tangent, right_tangent)
            error, split = _max_error(points, bezier, parameters)
            if error <= squared_tolerance:
                return [bezier]
    split = min(max(split, 1), len(points) - 2)
    center = _unit(_sub(points[split - 1], points[split + 1]))
    if center == (0.0, 0.0):
        center = _unit(_sub(points[split - 1], points[split]))
    left = _fit(points[: split + 1], left_tangent, center, tolerance, depth + 1)
    right = _fit(points[split:], _scale(center, -1), right_tangent, tolerance, depth + 1)
    return left + right


def _end_tangent(points: list[Point], reach: float) -> Point:
    """Direction leaving points[0], looking a little ahead so one noisy sample doesn't decide it."""
    for point in points[1:]:
        if _distance(point, points[0]) >= reach:
            return _unit(_sub(point, points[0]))
    return _unit(_sub(points[-1], points[0]))


def _fit_run(run: list[Point], reach: float, tolerance: float) -> list[Bezier]:
    left = _end_tangent(run, reach)
    right = _end_tangent(run[::-1], reach)
    if left == (0.0, 0.0) or right == (0.0, 0.0):
        return []
    return _fit(run, left, right, tolerance, 0)


def _fit_closed_without_corners(points: list[Point], reach: float, tolerance: float) -> list[Bezier]:
    """A loop with no corner gets one shared tangent at its seam, so it closes smoothly."""
    seam = _unit(_sub(points[1], points[-2]))
    if seam == (0.0, 0.0):
        return _fit_run(points, reach, tolerance)
    return _fit(points, seam, _scale(seam, -1), tolerance, 0)


# --- entry point -----------------------------------------------------------------------------------------


def fit_stroke(
    samples: Sequence[StrokeSample], smoothing: int, pixel_size: float, close_distance_px: float = 6.0
) -> tuple[tuple[Segment, ...], bool] | None:
    """(segments starting with MoveTo, closed) for a freehand stroke, or None if it's too short to be a path.

    `smoothing` (0 to 100) trades closeness for calm: the allowed deviation grows from 1 to 12 screen pixels and
    the stroke is pre-smoothed over up to 4 neighbouring points on each side."""
    if not samples:
        return None
    share = min(max(smoothing, 0), 100) / 100
    points = _decimate([(sample.x, sample.y) for sample in samples], _DECIMATE_PX * pixel_size)
    length = _length(points)
    if len(points) < 2 or length < _MIN_LENGTH_PX * pixel_size:
        return None
    close_distance = close_distance_px * pixel_size
    closed = len(points) >= 4 and _distance(points[0], points[-1]) <= close_distance and length > 4 * close_distance
    if closed:
        points[-1] = points[0]
    reach = _CORNER_REACH_PX * pixel_size
    tolerance = pixel_size * (1 + (_MAX_TOLERANCE_PX - 1) * share * share)
    window = round(_MAX_PRESMOOTH * share)

    if closed:
        loop = points[:-1]
        corners = _corners(loop, reach, cyclic=True)
        if corners:
            # Start the loop at a corner, so its seam is a corner too.
            first = corners[0]
            loop = loop[first:] + loop[:first]
            corners = sorted((index - first) % len(loop) for index in corners)
        points = loop + [loop[0]]
        boundaries = [*corners, len(points) - 1] if corners else []
        if not boundaries:
            beziers = _fit_closed_without_corners(_presmooth(points, window), reach, tolerance)
            return _segments(beziers, closed=True), True
    else:
        boundaries = [0, *_corners(points, reach, cyclic=False), len(points) - 1]

    beziers: list[Bezier] = []
    for start, end in zip(boundaries, boundaries[1:]):
        run = _presmooth(points[start : end + 1], window)
        beziers.extend(_fit_run(run, reach, tolerance))
    if not beziers:
        return None
    return _segments(beziers, closed), closed


def _segments(beziers: list[Bezier], closed: bool) -> tuple[Segment, ...]:
    segments: list[Segment] = [MoveTo(*beziers[0][0])]
    for _, first, second, end in beziers:
        segments.append(CubicTo(*first, *second, *end))
    if closed:
        segments.append(Close())
    return tuple(segments)
