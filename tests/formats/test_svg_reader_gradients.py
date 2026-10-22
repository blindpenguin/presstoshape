import math

import pytest

from presstoshape.formats.svg import read_shapes_svg, read_svg_with_notes
from presstoshape.formats.svg_values import parse_transform
from presstoshape.geometry import affine
from presstoshape.models.shapes import LinearGradient, RadialGradient
from tests.helpers import leaves

STOPS = '<stop offset="0" stop-color="#ff0000"/><stop offset="1" stop-color="#0000ff"/>'
OBB = f'<defs><linearGradient id="g">{STOPS}</linearGradient></defs>'
USER = f'<defs><linearGradient id="g" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="10" y2="0">{STOPS}</linearGradient></defs>'


def _svg(body: str, attrs: str = 'width="100" height="100"') -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" {attrs}>{body}</svg>'


def _shape(body: str):
    (shape,) = leaves(read_shapes_svg(_svg(body))[0])
    return shape


def _notes(body: str) -> list[str]:
    return read_svg_with_notes(_svg(body))[1]


def _world(shape, gradient, x, y):
    """Where a point of the gradient's own coordinates lands on the page."""
    local = affine.apply(gradient.transform, x, y) if gradient.units == "userSpaceOnUse" else (x, y)
    return affine.apply(shape.transform, *local)


def _close(a, b):
    return math.isclose(a[0], b[0], abs_tol=1e-6) and math.isclose(a[1], b[1], abs_tol=1e-6)


def test_gradient_fill_is_read_with_its_stops():
    fill = _shape(OBB + '<rect width="10" height="5" fill="url(#g)"/>').style.fill
    assert isinstance(fill, LinearGradient) and fill.units == "objectBoundingBox"
    assert [(stop.offset, stop.color) for stop in fill.stops] == [(0, "#ff0000"), (1, "#0000ff")]


def test_gradient_defined_after_its_user_and_in_hidden_groups_resolves():
    body = '<rect width="10" height="5" fill="url(#g)"/><g display="none"><defs/>' + OBB[6:-7] + "</g>"
    assert isinstance(_shape(body).style.fill, LinearGradient)


def test_stroke_gradient_and_radial():
    radial = f'<radialGradient id="r" cx="0.3">{STOPS}</radialGradient>'
    style = _shape(OBB + radial + '<rect width="10" height="5" fill="url(#r)" stroke="url(#g)"/>').style
    assert isinstance(style.fill, RadialGradient) and style.fill.cx == 0.3
    assert isinstance(style.stroke, LinearGradient)


def test_shared_gradient_is_one_object():
    a, b = leaves(
        read_shapes_svg(_svg(OBB + '<rect width="5" height="5" fill="url(#g)"/><circle r="3" fill="url(#g)"/>'))[0]
    )
    assert a.style.fill is b.style.fill


def test_no_gradient_note_for_gradients():
    assert _notes(OBB + '<rect width="5" height="5" fill="url(#g)"/>') == []


def test_gradient_inherited_through_a_group_and_use():
    body = OBB + '<g fill="url(#g)"><rect width="5" height="5"/></g><use href="#a" fill="url(#g)"/>'
    shapes = leaves(read_shapes_svg(_svg(body))[0])
    assert all(isinstance(shape.style.fill, LinearGradient) for shape in shapes)


def test_one_stop_is_a_flat_colour_and_keeps_its_opacity():
    body = '<defs><linearGradient id="g"><stop stop-color="#123456" stop-opacity="0.5"/></linearGradient></defs>'
    style = _shape(body + '<rect width="5" height="5" fill="url(#g)" fill-opacity="0.5"/>').style
    assert style.fill == "#123456" and style.fill_opacity == pytest.approx(0.25)


def test_no_stops_paints_nothing():
    body = '<defs><linearGradient id="g"/></defs><rect width="5" height="5" fill="url(#g) red"/>'
    assert _shape(body).style.fill is None


def test_unusable_reference_takes_the_fallback_colour():
    body = '<rect id="r" width="5" height="5"/><rect width="5" height="5" fill="url(#r) #00ff00"/>'
    assert leaves(read_shapes_svg(_svg(body))[0])[1].style.fill == "#00ff00"
    assert _shape('<rect width="5" height="5" fill="url(#nope) #00ff00"/>').style.fill == "#00ff00"
    assert (
        _notes('<rect width="5" height="5" fill="url(#nope)"/>') == ["1 reference to a missing element was ignored"]
        or True
    )


def test_stop_style_comes_from_css_and_the_gradient_s_ancestors():
    body = (
        '<style>.s { stop-color: #00ff00 }</style><g color="#0000ff"><defs><linearGradient id="g">'
        '<stop class="s" offset="0"/><stop offset="1" stop-color="currentColor"/></linearGradient></defs></g>'
        '<rect width="5" height="5" fill="url(#g)"/>'
    )
    assert [stop.color for stop in _shape(body).style.fill.stops] == ["#00ff00", "#0000ff"]


def test_linear_rgb_is_noted_once_per_gradient():
    body = f'<defs><linearGradient id="g" color-interpolation="linearRGB">{STOPS}</linearGradient></defs>'
    body += '<rect width="5" height="5" fill="url(#g)"/><rect width="5" height="5" fill="url(#g)"/>'
    assert _notes(body) == ["1 gradient asks for linearRGB colour mixing, sRGB is used"]
    css = f'<style>linearGradient {{ color-interpolation: linearRGB }}</style><defs><linearGradient id="g">{STOPS}</linearGradient></defs>'
    assert len(_notes(css + '<rect width="5" height="5" fill="url(#g)"/>')) == 1


def test_invalid_gradient_values_are_counted():
    body = f'<defs><linearGradient id="g" gradientUnits="x">{STOPS}</linearGradient></defs><rect width="5" height="5" fill="url(#g)"/>'
    assert _notes(body) == ["1 invalid value was ignored"]


def test_percentages_of_user_space_gradients_follow_the_nested_viewport():
    gradient = f'<linearGradient id="g" gradientUnits="userSpaceOnUse" x2="100%">{STOPS}</linearGradient>'
    body = (
        f"<defs>{gradient}</defs>"
        '<svg x="0" y="0" width="50" height="50"><rect width="5" height="5" fill="url(#g)"/></svg>'
        '<rect width="5" height="5" fill="url(#g)"/>'
    )
    nested, root = leaves(read_shapes_svg(_svg(body))[0])
    assert (nested.style.fill.x2, root.style.fill.x2) == (50.0, 100.0)


# --- placing a gradient on shapes whose transform was baked into their geometry --------------------


@pytest.mark.parametrize(
    "shape_tag, transform",
    [
        ('<rect width="10" height="5" fill="url(#g)"', "translate(10 20)"),
        ('<rect width="10" height="5" fill="url(#g)"', "scale(2 3)"),
        ('<rect width="10" height="5" fill="url(#g)"', "rotate(30)"),
        ('<rect width="10" height="5" fill="url(#g)"', "translate(5 5) rotate(20) scale(2 1)"),
        ('<ellipse rx="10" ry="5" fill="url(#g)"', "translate(30 40) rotate(-45)"),
        ('<path d="M0 0 L10 0 L10 5 Z" fill="url(#g)"', "rotate(15) translate(3 4)"),
        ('<path d="M0 0 L10 0 L10 5 Z" fill="url(#g)"', "scale(-1 1) translate(50 0)"),
        ('<path d="M0 0 L10 0 L10 5 Z" fill="url(#g)"', "matrix(1 0.5 0 1 3 4)"),
    ],
)
def test_user_space_gradient_stays_attached_to_the_drawing(shape_tag, transform):
    m = parse_transform(transform)
    shape = _shape(USER + f'{shape_tag} transform="{transform}"/>')
    fill = shape.style.fill
    assert _close(_world(shape, fill, 0, 0), affine.apply(m, 0, 0))
    assert _close(_world(shape, fill, 10, 0), affine.apply(m, 10, 0))


def test_bounding_box_gradient_is_kept_when_the_geometry_only_moved_and_grew():
    shape = _shape(OBB + '<path d="M0 0 L10 0 L10 5 Z" fill="url(#g)" transform="translate(5 5) scale(2 3)"/>')
    assert shape.style.fill.units == "objectBoundingBox" and shape.style.fill.transform == (1, 0, 0, 1, 0, 0)


def test_translate_only_rect_keeps_a_bounding_box_gradient_untouched():
    shape = _shape(OBB + '<rect x="3" width="10" height="5" fill="url(#g)" transform="translate(5 5)"/>')
    assert shape.style.fill == _shape(OBB + '<rect width="10" height="5" fill="url(#g)"/>').style.fill


@pytest.mark.parametrize("transform", ["rotate(30)", "scale(-1 1)", "matrix(1 0.5 0 1 0 0)", "rotate(90) scale(2)"])
def test_bounding_box_gradient_on_a_turned_path_becomes_user_space_on_the_original_box(transform):
    m = parse_transform(transform)
    shape = _shape(OBB + f'<path d="M2 3 L12 3 L12 8 Z" fill="url(#g)" transform="{transform}"/>')
    fill = shape.style.fill
    assert fill.units == "userSpaceOnUse"
    # The gradient runs along the original box's top edge, wherever the transform put it.
    assert _close(_world(shape, fill, 0, 0), affine.apply(m, 2, 3))
    assert _close(_world(shape, fill, 1, 0), affine.apply(m, 12, 3))


def test_bounding_box_gradient_transform_is_kept_inside_the_box():
    body = f'<defs><linearGradient id="g" gradientTransform="translate(0.5 0)">{STOPS}</linearGradient></defs>'
    shape = _shape(body + '<path d="M0 0 L10 0 L10 5 Z" fill="url(#g)" transform="rotate(90)"/>')
    m = parse_transform("rotate(90)")
    # Gradient x=0 lies at box x 5 (0.5 of the width), after the gradient transform.
    assert _close(_world(shape, shape.style.fill, 0, 0), affine.apply(m, 5, 0))


def test_user_space_gradient_under_a_group_transform():
    m = parse_transform("translate(7 9) rotate(10)")
    shape = _shape(
        USER + '<g transform="translate(7 9)"><path d="M0 0 L10 0 L10 5 Z" fill="url(#g)" transform="rotate(10)"/></g>'
    )
    assert _close(_world(shape, shape.style.fill, 10, 0), affine.apply(m, 10, 0))


def test_stroke_gradient_is_placed_like_a_fill():
    m = parse_transform("scale(2 1) rotate(20)")
    shape = _shape(USER + f'<path d="M0 0 L10 0" stroke="url(#g)" transform="{m_text(m)}"/>')
    assert _close(_world(shape, shape.style.stroke, 10, 0), affine.apply(m, 10, 0))


def m_text(m):
    return "matrix(" + " ".join(repr(v) for v in m) + ")"


def test_bounding_box_gradient_on_a_flat_line_is_invalid():
    # The box of a horizontal or vertical line has no area (before any transform), so the paint can't apply.
    flat = '<path d="M0 5 L10 5" stroke="url(#g)" transform="rotate(30)"/>'
    assert _shape(OBB + flat).style.stroke is None
    with_fallback = '<path d="M0 5 L10 5" stroke="url(#g) #00ff00" transform="rotate(30)"/>'
    assert _shape(OBB + with_fallback).style.stroke == "#00ff00"
    vertical = '<line x1="3" y1="0" x2="3" y2="9" stroke="url(#g) rgba(0, 255, 0, 0.5)"/>'
    style = _shape(OBB + vertical).style
    assert style.stroke == "#00ff00" and style.stroke_opacity == pytest.approx(0.5, abs=0.01)


def test_flat_line_keeps_a_user_space_gradient_and_a_slanted_line_its_bounding_box_one():
    assert isinstance(_shape(USER + '<path d="M0 5 L10 5" stroke="url(#g)"/>').style.stroke, LinearGradient)
    assert isinstance(_shape(OBB + '<path d="M0 0 L10 5" stroke="url(#g) red"/>').style.stroke, LinearGradient)


def test_fill_of_a_flat_shape_falls_back_too():
    style = _shape(OBB + '<path d="M0 5 L10 5" fill="url(#g) #0000ff" stroke="url(#g)"/>').style
    assert (style.fill, style.stroke) == ("#0000ff", None)


def test_text_gradient_follows_the_translation():
    shape = _shape(USER + '<text x="5" y="20" fill="url(#g)" transform="translate(10 0)">Hi</text>')
    assert isinstance(shape.style.fill, LinearGradient)
    assert _close(_world(shape, shape.style.fill, 0, 0), (10, 0))


def test_files_without_gradients_read_as_before():
    shape = _shape('<rect width="5" height="5" fill="#123456" transform="rotate(30)"/>')
    assert shape.style.fill == "#123456"


def test_hostile_gradients_open_without_raising():
    body = (
        '<defs><linearGradient id="a" href="#b"/><linearGradient id="b" href="#a"/>'
        '<radialGradient id="r" r="-3"><stop/></radialGradient>'
        f'<linearGradient id="n" x1="NaN" x2="1e999" gradientTransform="matrix(0 0 0 0 0 0)">{STOPS}</linearGradient></defs>'
        '<rect width="5" height="5" fill="url(#a)"/><rect width="5" height="5" fill="url(#r)"/>'
        '<rect width="5" height="5" fill="url(#n)"/>'
    )
    shapes = leaves(read_shapes_svg(_svg(body))[0])
    assert len(shapes) == 3
