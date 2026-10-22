import math

from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    MAX_STOPS,
    GradientStop,
    LinearGradient,
    RadialGradient,
    Style,
    flat_color,
    sanitized,
)


def test_default_style_is_already_sanitized():
    assert sanitized(Style()) == Style()


def test_opacities_are_clamped():
    style = sanitized(Style(opacity=2, fill_opacity=-1, stroke_opacity=math.nan))
    assert (style.opacity, style.fill_opacity, style.stroke_opacity) == (1, 0, 1)


def test_unknown_enum_values_fall_back_to_defaults():
    style = sanitized(Style(fill_rule="odd", cap="pointy", join="glued"))
    assert (style.fill_rule, style.cap, style.join) == ("nonzero", "butt", "miter")


def test_odd_dash_lists_are_repeated():
    assert sanitized(Style(dashes=(4, 2, 1))).dashes == (4, 2, 1, 4, 2, 1)


def test_invalid_dash_lists_become_solid():
    assert sanitized(Style(dashes=(4, -2))).dashes == ()
    assert sanitized(Style(dashes=(0, 0))).dashes == ()
    assert sanitized(Style(dashes=(math.inf, 1))).dashes == ()


def test_numbers_are_kept_in_range():
    style = sanitized(Style(stroke_width=-3, miter_limit=0.2, dash_offset=math.nan))
    assert (style.stroke_width, style.miter_limit, style.dash_offset) == (0, 1, 0)


def test_shapes_start_shown_and_unlocked_with_positional_constructors():
    from presstoshape.models.app_state import Layer
    from presstoshape.models.shapes import (
        IDENTITY_TRANSFORM,
        CompositeShape,
        EllipseShape,
        GroupShape,
        PathShape,
        RectShape,
        TextShape,
    )

    rect = RectShape(1, 0, 0, 10, 10, Style(), IDENTITY_TRANSFORM, 2, 3)
    shapes = [
        rect,
        EllipseShape(2, 5, 5, 5, 5, Style(), IDENTITY_TRANSFORM),
        PathShape(3, (), Style(), IDENTITY_TRANSFORM),
        TextShape(4, 0, 0, "Hi", 12, Style(), IDENTITY_TRANSFORM, "middle"),
        CompositeShape(5, (rect,), ("add",), Style(), IDENTITY_TRANSFORM),
        GroupShape(6, (rect,), 0.5, IDENTITY_TRANSFORM),
    ]
    assert (rect.rx, rect.ry) == (2, 3)
    assert all(not shape.hidden and not shape.locked for shape in shapes)
    assert not Layer("L", True, []).locked


def _linear(stops=(GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff")), **changes):
    return LinearGradient(**{"x1": 0, "y1": 0, "x2": 1, "y2": 0, "stops": stops} | changes)


def _radial(**changes):
    fields = {
        "cx": 0.5,
        "cy": 0.5,
        "r": 0.5,
        "fx": 0.5,
        "fy": 0.5,
        "stops": (GradientStop(0, "#fff"), GradientStop(1, "#000")),
    }
    return RadialGradient(**(fields | changes))


def test_gradients_compare_and_hash_by_value():
    assert _linear() == _linear()
    assert hash(_linear()) == hash(_linear())
    assert _linear() != _linear(spread="repeat")
    assert Style(fill=_linear()) == Style(fill=_linear())


def test_valid_gradients_are_left_alone():
    style = Style(fill=_linear(), stroke=_radial(units="userSpaceOnUse", spread="reflect"))
    assert sanitized(style) == style


def test_stop_offsets_are_clamped_and_never_decrease():
    stops = (GradientStop(-1, "#000"), GradientStop(0.6, "#111"), GradientStop(0.2, "#222"), GradientStop(5, "#333"))
    result = sanitized(Style(fill=_linear(stops))).fill
    assert [stop.offset for stop in result.stops] == [0, 0.6, 0.6, 1]


def test_stop_opacity_is_clamped_and_nan_offset_follows_previous():
    stops = (GradientStop(0.3, "#000", 2.0), GradientStop(math.nan, "#111", -1.0))
    result = sanitized(Style(fill=_linear(stops))).fill
    assert [(stop.offset, stop.opacity) for stop in result.stops] == [(0.3, 1.0), (0.3, 0.0)]


def test_too_many_stops_are_cut():
    stops = tuple(GradientStop(i / 5000, "#000") for i in range(5000))
    assert len(sanitized(Style(fill=_linear(stops))).fill.stops) == MAX_STOPS


def test_gradient_without_stops_is_no_paint():
    style = sanitized(Style(fill=_linear(()), stroke=_radial(stops=())))
    assert (style.fill, style.stroke) == (None, None)


def test_unknown_enums_and_non_finite_numbers_reset():
    result = sanitized(Style(fill=_linear(units="px", spread="wrap", x2=math.nan, y1=math.inf))).fill
    assert (result.units, result.spread, result.x2, result.y1) == ("objectBoundingBox", "pad", 1.0, 0.0)


def test_negative_radius_is_no_paint():
    assert sanitized(Style(fill=_radial(r=-1))).fill is None
    assert sanitized(Style(fill=_radial(r=math.nan))).fill is None


def test_focal_point_outside_the_circle_moves_onto_it():
    result = sanitized(Style(fill=_radial(fx=2.5, fy=0.5))).fill
    assert (result.fx, result.fy) == (1.0, 0.5)


def test_non_invertible_transform_becomes_identity():
    assert sanitized(Style(fill=_linear(transform=(0, 0, 0, 0, 5, 5)))).fill.transform == IDENTITY_TRANSFORM
    assert sanitized(Style(fill=_linear(transform=(math.nan, 0, 0, 1, 0, 0)))).fill.transform == IDENTITY_TRANSFORM


def test_flat_color():
    assert flat_color("#123456") == "#123456"
    assert flat_color(None) is None
    assert flat_color(_linear()) == "#ff0000"
