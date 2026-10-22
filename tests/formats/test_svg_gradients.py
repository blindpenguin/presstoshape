import xml.etree.ElementTree as ET

import pytest

from presstoshape.formats.svg_gradients import MAX_CHAIN, gradient_chain, resolve_gradient
from presstoshape.formats.svg_lengths import Viewport
from presstoshape.models.shapes import MAX_STOPS, GradientStop, LinearGradient, RadialGradient

VIEWPORT = Viewport(200.0, 100.0)
RED_BLUE = '<stop offset="0" stop-color="#ff0000"/><stop offset="1" stop-color="#0000ff"/>'


def _defs(body: str) -> dict[str, ET.Element]:
    root = ET.fromstring(
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">{body}</svg>'
    )
    return {element.get("id"): element for element in root.iter() if element.get("id")}


def _stop_style(element: ET.Element) -> dict[str, str]:
    style = {key: value for key, value in element.attrib.items() if key in ("stop-color", "stop-opacity", "color")}
    for declaration in element.get("style", "").split(";"):
        if ":" in declaration:
            key, _sep, value = declaration.partition(":")
            style[key.strip()] = value.strip()
    return style


def _resolve(body: str, target: str = "g", viewport: Viewport = VIEWPORT):
    ids = _defs(body)
    return resolve_gradient(ids[target], ids, _stop_style, viewport)


def _linear(attributes: str = "", stops: str = RED_BLUE):
    return _resolve(f'<linearGradient id="g" {attributes}>{stops}</linearGradient>')


def test_linear_defaults():
    paint = _linear().paint
    assert paint == LinearGradient(0.0, 0.0, 1.0, 0.0, (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff")))


def test_radial_defaults_focus_follows_centre():
    paint = _resolve(f'<radialGradient id="g">{RED_BLUE}</radialGradient>').paint
    assert (paint.cx, paint.cy, paint.r, paint.fx, paint.fy) == (0.5, 0.5, 0.5, 0.5, 0.5)
    moved = _resolve(f'<radialGradient id="g" cx="0.2" cy="0.3">{RED_BLUE}</radialGradient>').paint
    assert (moved.fx, moved.fy) == (0.2, 0.3)


def test_percentages_and_numbers_in_bounding_box_units():
    paint = _linear('x1="10%" y1="0.25" x2="75%" y2="100%"').paint
    assert (paint.x1, paint.y1, paint.x2, paint.y2) == (0.1, 0.25, 0.75, 1.0)


def test_user_space_percentages_use_the_viewport():
    paint = _linear('gradientUnits="userSpaceOnUse" x2="50%" y1="10%" y2="10%"').paint
    assert (paint.x1, paint.x2, paint.y1) == (0.0, 100.0, 10.0)
    radial = _resolve(f'<radialGradient id="g" gradientUnits="userSpaceOnUse">{RED_BLUE}</radialGradient>').paint
    assert (radial.cx, radial.cy) == (100.0, 50.0)


def test_units_spread_and_transform():
    paint = _linear(
        'gradientUnits="userSpaceOnUse" spreadMethod="reflect" gradientTransform="translate(5 6)" x2="9"'
    ).paint
    assert (paint.units, paint.spread, paint.transform) == ("userSpaceOnUse", "reflect", (1, 0, 0, 1, 5, 6))


def test_invalid_enums_fall_back_and_are_counted():
    result = _linear('gradientUnits="meters" spreadMethod="wrap"')
    assert (result.paint.units, result.paint.spread, result.invalid) == ("objectBoundingBox", "pad", 2)


def test_invalid_length_takes_the_default_and_is_counted():
    result = _linear('x2="lots"')
    assert result.paint.x2 == 1.0 and result.invalid == 1


def test_href_inherits_attributes_and_stops():
    ids = _defs(
        f'<linearGradient id="base" x1="0.1" x2="0.9" spreadMethod="repeat">{RED_BLUE}</linearGradient>'
        '<linearGradient id="g" href="#base" x2="0.5"/>'
    )
    paint = resolve_gradient(ids["g"], ids, _stop_style, VIEWPORT).paint
    assert (paint.x1, paint.x2, paint.spread) == (0.1, 0.5, "repeat")
    assert len(paint.stops) == 2


def test_own_stops_win_over_inherited_ones():
    ids = _defs(
        f'<linearGradient id="base">{RED_BLUE}</linearGradient>'
        '<linearGradient id="g" xlink:href="#base"><stop offset="0.5" stop-color="#00ff00"/>'
        '<stop offset="1" stop-color="#ffffff"/></linearGradient>'
    )
    paint = resolve_gradient(ids["g"], ids, _stop_style, VIEWPORT).paint
    assert [stop.color for stop in paint.stops] == ["#00ff00", "#ffffff"]


def test_attributes_come_from_the_same_type_only_but_stops_and_units_from_any():
    ids = _defs(
        f'<radialGradient id="base" cx="0.9" r="0.1" gradientUnits="userSpaceOnUse">{RED_BLUE}</radialGradient>'
        '<linearGradient id="g" href="#base"/>'
    )
    paint = resolve_gradient(ids["g"], ids, _stop_style, VIEWPORT).paint
    assert isinstance(paint, LinearGradient)
    assert paint.units == "userSpaceOnUse" and (paint.x2, len(paint.stops)) == (200.0, 2)


def test_href_cycle_and_depth_do_not_loop():
    ids = _defs('<linearGradient id="a" href="#b"/><linearGradient id="b" href="#a">' + RED_BLUE + "</linearGradient>")
    assert len(gradient_chain(ids["a"], ids)) == 2
    assert resolve_gradient(ids["a"], ids, _stop_style, VIEWPORT).paint is not None
    chain = "".join(f'<linearGradient id="n{i}" href="#n{i + 1}"/>' for i in range(100))
    ids = _defs(chain + f'<linearGradient id="n100">{RED_BLUE}</linearGradient>')
    assert len(gradient_chain(ids["n0"], ids)) == MAX_CHAIN
    assert resolve_gradient(ids["n0"], ids, _stop_style, VIEWPORT).paint is None


def test_href_to_a_non_gradient_ends_the_chain():
    ids = _defs(f'<rect id="r"/><linearGradient id="g" href="#r">{RED_BLUE}</linearGradient>')
    assert len(gradient_chain(ids["g"], ids)) == 1


def test_non_gradient_target_is_not_resolved():
    ids = _defs('<rect id="r"/><pattern id="p"/>')
    assert resolve_gradient(ids["r"], ids, _stop_style, VIEWPORT) is None
    assert resolve_gradient(ids["p"], ids, _stop_style, VIEWPORT) is None


def test_no_stops_is_no_paint():
    result = _linear(stops="")
    assert result.paint is None


def test_one_stop_is_a_flat_colour_with_its_opacity():
    result = _linear(stops='<stop offset="0.3" stop-color="#123456" stop-opacity="0.5"/>')
    assert (result.paint, result.opacity) == ("#123456", 0.5)


def test_degenerate_vectors_use_the_last_stop():
    result = _linear('x1="0.5" x2="0.5" y1="0.2" y2="0.2"')
    assert result.paint == "#0000ff"
    radial = _resolve(f'<radialGradient id="g" r="0">{RED_BLUE}</radialGradient>')
    assert radial.paint == "#0000ff"


def test_negative_radius_is_invalid():
    assert _resolve(f'<radialGradient id="g" r="-1">{RED_BLUE}</radialGradient>') is None


def test_focal_point_outside_the_circle_is_pulled_in():
    paint = _resolve(f'<radialGradient id="g" fx="2" fy="0.5">{RED_BLUE}</radialGradient>').paint
    assert (paint.fx, paint.fy) == (1.0, 0.5)


def test_stop_offsets_percent_clamp_and_never_decrease():
    stops = (
        '<stop offset="50%" stop-color="#000"/><stop offset="0.2" stop-color="#111"/>'
        '<stop offset="3" stop-color="#222"/><stop offset="-1" stop-color="#333"/>'
    )
    assert [stop.offset for stop in _linear(stops=stops).paint.stops] == [0.5, 0.5, 1.0, 1.0]


def test_bad_offset_counts_and_missing_offset_is_zero():
    result = _linear(stops='<stop offset="far" stop-color="#000"/><stop stop-color="#fff"/>')
    assert result.invalid == 1
    assert [stop.offset for stop in result.paint.stops] == [0.0, 0.0]


def test_stop_colour_sources():
    stops = (
        '<stop offset="0" style="stop-color:#00ff00;stop-opacity:0.5"/>'
        '<stop offset="0.5" stop-color="currentColor" color="#ff00ff"/>'
        '<stop offset="1" stop-color="rgba(255, 0, 0, 0.5)" stop-opacity="50%"/>'
    )
    stops = _linear(stops=stops).paint.stops
    assert [(stop.color, stop.opacity) for stop in stops[:2]] == [("#00ff00", 0.5), ("#ff00ff", 1.0)]
    assert stops[2].color == "#ff0000" and abs(stops[2].opacity - 0.25) < 0.01


def test_missing_stop_colour_is_black_and_transparent_is_clear():
    stops = _linear(stops='<stop offset="0"/><stop offset="1" stop-color="transparent"/>').paint.stops
    assert [(stop.color, stop.opacity) for stop in stops] == [("#000000", 1.0), ("#000000", 0.0)]


def test_non_stop_children_are_ignored():
    stops = _linear(stops='<title>t</title><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/>')
    assert len(stops.paint.stops) == 2


def test_stop_count_is_capped_and_counted():
    result = _linear(stops='<stop offset="0.5" stop-color="#000"/>' * (MAX_STOPS + 50))
    assert len(result.paint.stops) == MAX_STOPS and result.invalid == 1


def test_linear_rgb_is_reported():
    assert _linear('color-interpolation="linearRGB"').linear_rgb
    assert not _linear().linear_rgb


@pytest.mark.parametrize("attributes", ['x1="1e999"', 'x1="NaN"', 'gradientTransform="matrix(0 0 0 0 0 0)"'])
def test_hostile_values_never_raise_and_stay_finite(attributes):
    paint = _linear(attributes).paint
    assert isinstance(paint, LinearGradient)
    assert all(abs(v) < 1e9 for v in (paint.x1, paint.y1, paint.x2, paint.y2, *paint.transform))


def test_resolved_paint_is_a_fixed_value_for_equal_input():
    assert _linear().paint == _linear().paint
    assert isinstance(_resolve(f'<radialGradient id="g">{RED_BLUE}</radialGradient>').paint, RadialGradient)
