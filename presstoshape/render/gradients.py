"""Gradient paints as Skia shaders."""

import skia

from presstoshape.models.shapes import Gradient, GradientStop, LinearGradient, RadialGradient

_TILES = {"pad": skia.TileMode.kClamp, "reflect": skia.TileMode.kMirror, "repeat": skia.TileMode.kRepeat}


def _color(stop: GradientStop) -> int:
    rgb = int(stop.color.lstrip("#")[:6], 16)
    return (round(stop.opacity * 255) << 24) | rgb


def _colors_and_positions(stops: tuple[GradientStop, ...]) -> tuple[list[int], list[float]]:
    """Skia wants positions from 0 to 1; SVG paints before the first and after the last stop in their colour."""
    colors = [_color(stop) for stop in stops]
    positions = [stop.offset for stop in stops]
    if positions[0] > 0:
        colors.insert(0, colors[0])
        positions.insert(0, 0.0)
    if positions[-1] < 1:
        colors.append(colors[-1])
        positions.append(1.0)
    return colors, positions


def gradient_shader(paint: Gradient, bounds: skia.Rect) -> skia.Shader | None:
    """`bounds` is the shape's geometry box in its own coordinates (no stroke). None when there is nothing to
    draw: an objectBoundingBox gradient on a box without width or height."""
    a, b, c, d, e, f = paint.transform
    matrix = skia.Matrix.MakeAll(a, c, e, b, d, f, 0, 0, 1)
    if paint.units == "objectBoundingBox":
        if bounds.width() <= 0 or bounds.height() <= 0:
            return None
        box = skia.Matrix.MakeAll(bounds.width(), 0, bounds.left(), 0, bounds.height(), bounds.top(), 0, 0, 1)
        matrix = skia.Matrix.Concat(box, matrix)
    colors, positions = _colors_and_positions(paint.stops)
    mode = _TILES.get(paint.spread, skia.TileMode.kClamp)
    match paint:
        case LinearGradient(x1=x1, y1=y1, x2=x2, y2=y2):
            return skia.GradientShader.MakeLinear(
                [skia.Point(x1, y1), skia.Point(x2, y2)], colors, positions, mode, 0, matrix
            )
        case RadialGradient(cx=cx, cy=cy, r=r, fx=fx, fy=fy):
            if (fx, fy) == (cx, cy):
                return skia.GradientShader.MakeRadial(skia.Point(cx, cy), r, colors, positions, mode, 0, matrix)
            return skia.GradientShader.MakeTwoPointConical(
                skia.Point(fx, fy), 0, skia.Point(cx, cy), r, colors, positions, mode, 0, matrix
            )
