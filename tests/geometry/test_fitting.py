import math
import random
import time

import pytest

from presstoshape.geometry.fitting import StrokeSample, fit_stroke
from presstoshape.models.shapes import Close, CubicTo, MoveTo


def _samples(points) -> list[StrokeSample]:
    return [StrokeSample(x, y) for x, y in points]


def _bezier_point(start, segment, t):
    mt = 1 - t
    xs = (start[0], segment.c1x, segment.c2x, segment.x)
    ys = (start[1], segment.c1y, segment.c2y, segment.y)
    weights = (mt**3, 3 * mt * mt * t, 3 * mt * t * t, t**3)
    return sum(w * x for w, x in zip(weights, xs)), sum(w * y for w, y in zip(weights, ys))


def _curve_points(segments, steps=40):
    points, start = [], None
    for segment in segments:
        if isinstance(segment, MoveTo):
            start = (segment.x, segment.y)
        elif isinstance(segment, CubicTo):
            points.extend(_bezier_point(start, segment, step / steps) for step in range(steps + 1))
            start = (segment.x, segment.y)
    return points


def _cubics(segments):
    return [segment for segment in segments if isinstance(segment, CubicTo)]


def _max_deviation(points, segments):
    curve = _curve_points(segments, 80)
    return max(min(math.dist(point, on_curve) for on_curve in curve) for point in points)


def _circle(count=200, radius=100.0, noise=0.0, seed=1):
    rng = random.Random(seed)
    return [
        (
            200 + radius * math.cos(2 * math.pi * i / count) + rng.uniform(-noise, noise),
            200 + radius * math.sin(2 * math.pi * i / count) + rng.uniform(-noise, noise),
        )
        for i in range(count + 1)
    ]


def _tangent_mismatch(segments):
    """Largest angle (degrees) between incoming and outgoing tangents at joins between cubics."""
    cubics = _cubics(segments)
    worst = 0.0
    for before, after in zip(cubics, cubics[1:]):
        incoming = (before.x - before.c2x, before.y - before.c2y)
        outgoing = (after.c1x - before.x, after.c1y - before.y)
        cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
        dot = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
        angle = math.degrees(abs(math.atan2(cross, dot)))
        worst = max(worst, angle)
    return worst


def test_straight_line_is_one_curve():
    segments, closed = fit_stroke(_samples([(x, 10.0) for x in range(0, 200, 2)]), 50, 1.0)
    assert not closed and len(_cubics(segments)) == 1
    assert isinstance(segments[0], MoveTo) and (segments[0].x, segments[0].y) == (0, 10)


@pytest.mark.parametrize("noise", [0.0, 1.5])
def test_circle_closes_with_few_curves_within_tolerance(noise):
    points = _circle(noise=noise)
    segments, closed = fit_stroke(_samples(points), 50, 1.0)
    assert closed and isinstance(segments[-1], Close)
    assert len(_cubics(segments)) <= 8
    assert _max_deviation(points, segments) <= 3.5 + noise
    assert _tangent_mismatch(segments) < 2


def test_corners_stay_corners_and_curves_join_smoothly():
    corner = [(x, 0.0) for x in range(0, 101, 2)] + [(100.0, y) for y in range(2, 101, 2)]
    segments, _closed = fit_stroke(_samples(corner), 50, 1.0)
    assert _tangent_mismatch(segments) > 80
    wave = [(x, 40 * math.sin(x / 30)) for x in range(0, 400, 2)]
    segments, _closed = fit_stroke(_samples(wave), 50, 1.0)
    assert len(_cubics(segments)) >= 2
    assert _tangent_mismatch(segments) < 2


def test_stays_within_tolerance_and_smoothing_reduces_nodes():
    rng = random.Random(3)
    wobbly = [(x, 30 * math.sin(x / 25) + rng.uniform(-2, 2)) for x in range(0, 500, 2)]
    exact, _ = fit_stroke(_samples(wobbly), 0, 1.0)
    calm, _ = fit_stroke(_samples(wobbly), 100, 1.0)
    assert _max_deviation(wobbly, exact) <= 1.6
    assert len(_cubics(calm)) < len(_cubics(exact))


def test_too_short_or_degenerate_strokes_give_nothing():
    assert fit_stroke([], 50, 1.0) is None
    assert fit_stroke(_samples([(5, 5)] * 20), 50, 1.0) is None
    assert fit_stroke(_samples([(0, 0), (1, 1)]), 50, 1.0) is None


def test_same_stroke_at_another_zoom_gives_the_same_curve_count():
    rng = random.Random(4)
    stroke = [(x, 20 * math.sin(x / 15) + rng.uniform(-1, 1)) for x in range(0, 300, 2)]
    near, _ = fit_stroke(_samples(stroke), 50, 1.0)
    far, _ = fit_stroke(_samples([(x * 4, y * 4) for x, y in stroke]), 50, 4.0)
    assert len(_cubics(near)) == len(_cubics(far))


def test_no_overshooting_handles():
    rng = random.Random(5)
    scribble = [(x * 3 + rng.uniform(-3, 3), rng.uniform(-40, 40)) for x in range(120)]
    segments, _ = fit_stroke(_samples(scribble), 50, 1.0)
    xs = [x for x, _ in scribble]
    ys = [y for _, y in scribble]
    margin = 3 * max(max(xs) - min(xs), max(ys) - min(ys))
    for segment in _cubics(segments):
        for x, y in ((segment.c1x, segment.c1y), (segment.c2x, segment.c2y)):
            assert min(xs) - margin <= x <= max(xs) + margin and min(ys) - margin <= y <= max(ys) + margin


def test_long_strokes_fit_quickly():
    rng = random.Random(6)
    stroke = [
        (i * 0.4 + 30 * math.sin(i / 90), 60 * math.sin(i / 140) + rng.uniform(-1, 1)) for i in range(5000)
    ]
    started = time.perf_counter()
    result = fit_stroke(_samples(stroke), 50, 1.0)
    assert result is not None
    assert time.perf_counter() - started < 0.1
