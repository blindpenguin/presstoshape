"""Reading clip paths and masks: units, rules and the error cases of the SVG masking chapter."""

import math

import pytest

from presstoshape.formats.svg import read_shapes_svg, read_svg_with_notes
from presstoshape.formats.svg_masks import bbox_matrix, covers, parse_reference, shapes_box, unit_value
from presstoshape.geometry.transforms import area_outline
from presstoshape.models.shapes import (
    GroupShape,
    PathShape,
    RectShape,
    TextShape,
    content_children,
    mask_children,
)
from tests.helpers import leaves


def _svg(body: str, attrs: str = 'width="200" height="200"') -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" {attrs}>{body}</svg>'
    )


def _shapes(body: str, **kwargs) -> list:
    return read_shapes_svg(_svg(body, **kwargs))[0]


def _notes(body: str) -> list[str]:
    return read_svg_with_notes(_svg(body))[1]


def _one(body: str) -> GroupShape:
    (shape,) = _shapes(body)
    assert isinstance(shape, GroupShape) and shape.masking is not None, shape
    return shape


def _bounds(shape) -> tuple[float, float, float, float]:
    box = shapes_box([shape], (1, 0, 0, 1, 0, 0))
    return tuple(round(v, 6) for v in box)


# --- helpers ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, type, target",
    [
        (None, "none", None),
        ("none", "none", None),
        ("url(#a)", "url", "a"),
        ("url('#a')", "url", "a"),
        ('url( "#a" )', "url", "a"),
        ("circle(50%)", "unsupported", None),
        ("url(file.svg#a)", "unsupported", None),
    ],
)
def test_parse_reference(value, type, target):
    reference = parse_reference(value)
    assert (reference.type, reference.target) == (type, target)


def test_unit_value_and_box_helpers():
    assert (unit_value("25%", 0), unit_value(".5", 0), unit_value("x", 7), unit_value(None, 3)) == (0.25, 0.5, 7, 3)
    assert unit_value("inf", 4) == 4 and unit_value("nan", 4) == 4
    assert bbox_matrix((10, 20, 30, 40)) == (30, 0, 0, 40, 10, 20)
    assert covers((0, 0, 10, 10), (1, 1, 2, 2)) and not covers((0, 0, 10, 10), (5, 5, 10, 1))
    assert not covers((0, 0, 10, 10), None)


# --- clip paths ----------------------------------------------------------------------------------


CLIP = '<clipPath id="c"><rect x="20" y="20" width="40" height="40"/></clipPath>'


def test_clip_path_becomes_a_clipping_group():
    group = _one(CLIP + '<rect width="100" height="100" fill="red" clip-path="url(#c)"/>')
    assert group.masking.type == "clip" and not group.masking.inverted
    (content,), (mask,) = content_children(group), mask_children(group)
    assert (content.width, content.style.fill) == (100, "#ff0000")
    assert (mask.x, mask.width) == (20, 40)


def test_clip_path_in_defs_and_after_its_use():
    body = '<rect width="9" height="9" clip-path="url(#c)"/><defs>' + CLIP + "</defs>"
    assert len(mask_children(_one(body))) == 1


def test_clip_children_have_geometry_only():
    clip = '<clipPath id="c"><rect width="9" height="9" fill="none" stroke="red" stroke-width="30" opacity="0.2"/></clipPath>'
    (mask,) = mask_children(_one(clip + '<rect width="50" height="50" clip-path="url(#c)"/>'))
    assert (mask.style.fill, mask.style.stroke, mask.style.opacity) == ("#000000", None, 1.0)


def test_clip_rule_is_the_fill_rule_of_clip_children():
    d = "M0 0H50V50H0Z M10 10H40V40H10Z"
    clip = f'<clipPath id="c"><path d="{d}" clip-rule="evenodd" fill-rule="nonzero"/></clipPath>'
    (mask,) = mask_children(_one(clip + '<rect width="50" height="50" clip-path="url(#c)"/>'))
    assert mask.style.fill_rule == "evenodd"
    inherited = f'<clipPath id="c" clip-rule="evenodd"><path d="{d}"/></clipPath>'
    (mask,) = mask_children(_one(inherited + '<rect width="50" height="50" clip-path="url(#c)"/>'))
    assert mask.style.fill_rule == "evenodd"


def test_hidden_children_do_not_clip():
    clip = (
        '<clipPath id="c"><rect width="9" height="9" display="none"/><rect width="9" height="9" visibility="hidden"/>'
        '<rect x="5" width="9" height="9" opacity="0"/></clipPath>'
    )
    group = _one(clip + '<rect width="50" height="50" clip-path="url(#c)"/>')
    assert [shape.x for shape in mask_children(group)] == [5]


def test_only_shapes_text_and_use_count_in_a_clip_path():
    clip = '<clipPath id="c"><g><rect width="9" height="9"/></g><rect id="r" x="3" width="9" height="9"/><use href="#r"/></clipPath>'
    assert len(mask_children(_one(clip + '<rect width="50" height="50" clip-path="url(#c)"/>'))) == 2


def test_text_can_clip():
    clip = '<clipPath id="c"><text x="10" y="40" font-size="30">Hi</text></clipPath>'
    (mask,) = mask_children(_one(clip + '<rect width="50" height="50" clip-path="url(#c)"/>'))
    assert isinstance(mask, TextShape)


def test_user_space_clip_follows_the_transform_of_the_clipped_element():
    body = CLIP + '<rect width="100" height="100" transform="translate(50 0)" clip-path="url(#c)"/>'
    group = _one(body)
    (mask,) = mask_children(group)
    assert _bounds(mask) == (70, 20, 40, 40)


def test_clip_path_transform_applies_to_its_children():
    clip = '<clipPath id="c" transform="translate(10 5)"><rect width="9" height="9"/></clipPath>'
    (mask,) = mask_children(_one(clip + '<rect width="50" height="50" clip-path="url(#c)"/>'))
    assert _bounds(mask) == (10, 5, 9, 9)


def test_object_bounding_box_units():
    clip = '<clipPath id="c" clipPathUnits="objectBoundingBox"><rect x=".25" y=".5" width=".6" height="1"/></clipPath>'
    group = _one(clip + '<rect x="10" y="10" width="200" height="80" clip-path="url(#c)"/>')
    (mask,) = mask_children(group)
    assert _bounds(mask) == (60, 50, 120, 80)


def test_object_bounding_box_on_a_line_hides_the_element():
    clip = '<clipPath id="c" clipPathUnits="objectBoundingBox"><rect width="1" height="1"/></clipPath>'
    assert _shapes(clip + '<line x1="0" y1="5" x2="50" y2="5" stroke="red" clip-path="url(#c)"/>') == []


def test_clip_path_on_a_group_wraps_the_group():
    group = _one(CLIP + '<g clip-path="url(#c)"><rect width="9" height="9"/><circle r="5"/></g>')
    (inner,) = content_children(group)
    assert isinstance(inner, GroupShape) and inner.masking is None and len(inner.children) == 2


def test_clip_path_on_use_and_on_text():
    assert _one(CLIP + '<defs><rect id="r" width="9" height="9"/></defs><use href="#r" clip-path="url(#c)"/>')
    assert _one(CLIP + '<text x="1" y="30" clip-path="url(#c)">Hi</text>')


def test_clip_path_on_a_clip_child_clips_that_child_only():
    clip = (
        '<clipPath id="inner"><rect width="10" height="100"/></clipPath>'
        '<clipPath id="c"><rect width="100" height="100" clip-path="url(#inner)"/><rect x="150" width="9" height="9"/>'
        "</clipPath>"
    )
    group = _one(clip + '<rect width="200" height="200" clip-path="url(#c)"/>')
    first, second = mask_children(group)
    assert isinstance(first, GroupShape) and first.masking.type == "clip" and isinstance(second, RectShape)


def test_clip_path_on_a_clip_path_intersects():
    clip = (
        '<clipPath id="a"><rect width="100" height="100"/></clipPath>'
        '<clipPath id="c" clip-path="url(#a)"><rect x="50" width="100" height="100"/></clipPath>'
    )
    group = _one(clip + '<rect width="200" height="200" clip-path="url(#c)"/>')
    (cut,) = mask_children(group)
    assert isinstance(cut, GroupShape) and cut.masking.type == "clip"
    assert [c.width for c in mask_children(cut)] == [100]


def test_clipping_of_a_clip_path_ancestor_is_not_inherited():
    clip = '<clipPath id="a"><rect width="9" height="9"/></clipPath>'
    body = (
        clip + '<g clip-path="url(#a)"><clipPath id="c"><rect width="50" height="50"/></clipPath>'
        '<rect width="200" height="200" clip-path="url(#c)"/></g>'
    )
    (outer,) = _shapes(body)
    inner_group = content_children(outer)[0]
    (clipped,) = [child for child in inner_group.children if isinstance(child, GroupShape)]
    assert mask_children(clipped)[0].width == 50


def test_element_with_clip_and_mask_gets_two_groups():
    mask = '<mask id="m"><rect width="9" height="9" fill="white"/></mask>'
    outer = _one(CLIP + mask + '<rect width="50" height="50" clip-path="url(#c)" mask="url(#m)"/>')
    assert outer.masking.type == "clip"
    (inner,) = content_children(outer)
    assert inner.masking.type == "luminance"


def test_shared_clip_path_gives_each_user_its_own_objects():
    body = (
        CLIP + '<rect width="9" height="9" clip-path="url(#c)"/><rect x="50" width="9" height="9" clip-path="url(#c)"/>'
    )
    first, second = _shapes(body)
    ids = {shape.id for g in (first, second) for shape in g.children} | {first.id, second.id}
    assert len(ids) == 6


# --- errors and limits ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        '<rect width="5" height="5" clip-path="url(#nope)"/>',
        '<rect id="x" width="5" height="5"/><rect width="5" height="5" clip-path="url(#x)"/>',
        '<rect width="5" height="5" clip-path="circle(50%)"/>',
        '<mask id="m"/><rect width="5" height="5" clip-path="url(#m)"/>',
    ],
)
def test_unusable_clip_references_leave_the_element_unclipped_and_are_noted(body):
    shapes = _shapes(body)
    assert all(not isinstance(s, GroupShape) for s in shapes)
    assert "clip path was ignored" in _notes(body)[-1]


def test_unusable_mask_references_are_noted():
    body = '<rect width="5" height="5" mask="url(#nope)"/>'
    assert _notes(body) == ["1 mask was ignored, its content is shown unmasked"]


def test_empty_clip_path_clips_everything():
    group = _one('<clipPath id="c"/><rect width="50" height="50" clip-path="url(#c)"/>')
    assert mask_children(group) == () and len(content_children(group)) == 1


def test_clip_path_cycles_do_not_loop():
    body = (
        '<clipPath id="a" clip-path="url(#b)"><rect width="9" height="9"/></clipPath>'
        '<clipPath id="b" clip-path="url(#a)"><rect width="9" height="9"/></clipPath>'
        '<rect width="50" height="50" clip-path="url(#a)"/>'
    )
    assert _shapes(body)
    assert any("refers to itself" in note or "refer to themselves" in note for note in _notes(body))


def test_clip_path_that_uses_an_element_clipped_by_itself_does_not_loop():
    body = '<clipPath id="a"><use href="#r"/></clipPath><rect id="r" width="50" height="50" clip-path="url(#a)"/>'
    assert _shapes(body) is not None


def test_hostile_clip_input_is_survived():
    many = "".join(f'<rect x="{i}" width="1" height="1"/>' for i in range(5000))
    group = _one(f'<clipPath id="c">{many}</clipPath><rect width="50" height="50" clip-path="url(#c)"/>')
    assert len(mask_children(group)) == 4096
    nested = "".join(
        f'<clipPath id="n{i}" clip-path="url(#n{i + 1})"><rect width="9" height="9"/></clipPath>' for i in range(100)
    )
    assert _shapes(nested + '<rect width="5" height="5" clip-path="url(#n0)"/>')


def test_nan_and_infinite_geometry_never_leaks_into_clips():
    clip = '<clipPath id="c" transform="scale(1e999)"><rect width="9" height="9"/></clipPath>'
    for shape in leaves(_shapes(clip + '<rect width="50" height="50" clip-path="url(#c)"/>')):
        outline = area_outline(shape)
        if outline:
            assert all(math.isfinite(v) for segment in outline for v in vars(segment).values())


# --- masks ---------------------------------------------------------------------------------------


MASK = '<mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="200" height="200"><rect width="50" height="50" fill="white"/></mask>'


def test_mask_becomes_a_luminance_group_with_artwork():
    group = _one(MASK + '<rect width="100" height="100" fill="red" mask="url(#m)"/>')
    assert group.masking.type == "luminance"
    (mask,) = mask_children(group)
    assert (mask.style.fill, mask.width) == ("#ffffff", 50)


def test_mask_children_keep_their_paint_and_strokes():
    mask = '<mask id="m"><rect width="9" height="9" fill="none" stroke="#808080" stroke-width="3" fill-opacity="0.5"/></mask>'
    (child,) = mask_children(_one(mask + '<rect width="50" height="50" mask="url(#m)"/>'))
    assert (child.style.fill, child.style.stroke, child.style.stroke_width) == (None, "#808080", 3)


def test_mask_type_alpha_is_read_from_attribute_and_style():
    for form in ('mask-type="alpha"', 'style="mask-type:alpha"'):
        mask = f'<mask id="m" {form}><rect width="9" height="9"/></mask>'
        assert _one(mask + '<rect width="50" height="50" mask="url(#m)"/>').masking.type == "alpha"


def test_empty_mask_hides_the_content():
    group = _one('<mask id="m"/><rect width="50" height="50" mask="url(#m)"/>')
    assert group.masking.type == "luminance" and mask_children(group) == ()


def test_default_mask_region_is_around_the_bounding_box_and_dropped_when_it_cuts_nothing():
    mask = '<mask id="m"><rect x="10" y="10" width="100" height="100" fill="white"/></mask>'
    group = _one(mask + '<rect x="10" y="10" width="100" height="100" mask="url(#m)"/>')
    assert group.masking.region is None
    narrow = '<mask id="m" x="0" y="0" width="0.5" height="0.5"><rect x="-50" y="-50" width="400" height="400" fill="white"/></mask>'
    region = _one(narrow + '<rect x="10" y="10" width="100" height="100" mask="url(#m)"/>').masking.region
    assert region == pytest.approx((10, 10, 50, 50))


def test_user_space_mask_region():
    mask = '<mask id="m" maskUnits="userSpaceOnUse" x="20" y="30" width="40" height="50"><rect width="300" height="300" fill="white"/></mask>'
    region = _one(mask + '<rect width="100" height="100" mask="url(#m)"/>').masking.region
    assert region == (20, 30, 40, 50)


def test_region_follows_the_transform():
    mask = '<mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="10" height="10"><rect width="300" height="300" fill="white"/></mask>'
    region = _one(
        mask + '<rect width="50" height="50" transform="translate(5 6) scale(2)" mask="url(#m)"/>'
    ).masking.region
    assert region == (5, 6, 20, 20)


def test_mask_content_units_object_bounding_box():
    mask = '<mask id="m" maskContentUnits="objectBoundingBox"><rect width="0.5" height="0.5" fill="white"/></mask>'
    (child,) = mask_children(_one(mask + '<rect x="10" y="10" width="100" height="100" mask="url(#m)"/>'))
    assert _bounds(child) == (10, 10, 50, 50)


def test_mask_with_object_bounding_box_on_a_line_hides_the_element():
    assert _shapes('<mask id="m"/><line x1="0" y1="5" x2="50" y2="5" stroke="red" mask="url(#m)"/>') == []


def test_mask_gradients_and_nested_masks_are_read():
    body = (
        '<defs><linearGradient id="g"><stop offset="0" stop-color="black"/><stop offset="1" stop-color="white"/>'
        "</linearGradient></defs>"
        '<mask id="inner"><rect width="9" height="9" fill="white"/></mask>'
        '<mask id="m"><rect width="50" height="50" fill="url(#g)" mask="url(#inner)"/></mask>'
        '<rect width="100" height="100" mask="url(#m)"/>'
    )
    group = _one(body)
    (child,) = mask_children(group)
    assert isinstance(child, GroupShape) and child.masking.type == "luminance"
    assert content_children(child)[0].style.fill.stops


def test_mask_linear_rgb_is_noted_as_srgb():
    mask = '<mask id="m" color-interpolation="linearRGB"><rect width="9" height="9" fill="white"/></mask>'
    notes = _notes(mask + '<rect width="50" height="50" mask="url(#m)"/>')
    assert notes == ["1 mask asks for linearRGB colour mixing, sRGB is used"]


def test_mask_cycles_do_not_loop():
    body = '<mask id="m"><rect width="9" height="9" fill="white" mask="url(#m)"/></mask><rect width="50" height="50" mask="url(#m)"/>'
    assert _shapes(body)
    assert any("itself" in note or "themselves" in note for note in _notes(body))


def test_masks_are_never_drawn_where_they_stand():
    assert _shapes(MASK) == []
    assert _shapes(CLIP) == []


def test_hidden_element_with_a_clip_stays_hidden():
    (shape,) = _shapes(CLIP + '<rect width="9" height="9" display="none" clip-path="url(#c)"/>')
    assert shape.hidden


def test_clipped_paths_keep_working_with_path_elements():
    group = _one(CLIP + '<path d="M0 0H100V100H0Z" clip-path="url(#c)"/>')
    assert isinstance(content_children(group)[0], PathShape)
