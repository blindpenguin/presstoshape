"""Reading SVG from other programs: cascade, new style properties, <use>/<symbol>, text lines and notes."""

import time
from pathlib import Path

import pytest

from presstoshape.formats.svg import read_shapes_svg, read_svg, read_svg_with_notes, write_svg
from presstoshape.geometry import units
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.layout import GridSettings, Guide
from presstoshape.models.shapes import (
    EllipseShape,
    GradientStop,
    GroupShape,
    LinearGradient,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)
from tests.helpers import leaves

SAMPLES = Path(__file__).resolve().parent / "samples" / "svg"


def _svg(body: str, attrs: str = 'width="100" height="100"') -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" {attrs}>{body}</svg>'
    )


def _shapes(body: str) -> list:
    return read_shapes_svg(_svg(body))[0]


def _notes(body: str) -> list[str]:
    return read_svg_with_notes(_svg(body))[1]


def _style(body: str) -> Style:
    (shape,) = leaves(_shapes(body))
    return shape.style


# --- cascade --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        '<rect width="5" height="5" fill-rule="evenodd"/>',
        '<rect width="5" height="5" style="fill-rule: evenodd"/>',
        '<style>.a { fill-rule: evenodd }</style><rect class="a" width="5" height="5"/>',
        '<g fill-rule="evenodd"><rect width="5" height="5"/></g>',
        '<g style="fill-rule:evenodd"><g><rect width="5" height="5"/></g></g>',
    ],
)
def test_properties_come_from_attributes_inline_css_and_inheritance(body):
    assert _style(body).fill_rule == "evenodd"


def test_precedence_attribute_then_sheet_then_inline_then_important():
    sheet = "<style>#r { fill: green } rect { stroke: green !important }</style>"
    rect = '<rect id="r" width="5" height="5" fill="red" stroke="red" style="fill: blue; stroke: blue"/>'
    style = _style(sheet + rect)
    assert (style.fill, style.stroke) == ("#0000ff", "#008000")
    style = _style(sheet + '<rect id="r" width="5" height="5" fill="red" style="stroke: blue !important"/>')
    assert (style.fill, style.stroke) == ("#008000", "#0000ff")


def test_css_order_and_specificity_between_elements():
    sheet = "<style>rect { fill: red } .c { fill: green } #i { fill: blue }</style>"
    assert _style(sheet + '<rect class="c" width="5" height="5"/>').fill == "#008000"
    assert _style(sheet + '<rect class="c" id="i" width="5" height="5"/>').fill == "#0000ff"


def test_style_sheets_anywhere_and_in_cdata_apply():
    body = '<defs><style><![CDATA[ .a { fill: #00ff00 } ]]></style></defs><rect class="a" width="5" height="5"/>'
    assert _style(body).fill == "#00ff00"


def test_inherit_keeps_the_parent_value_and_classes_inherit_through_groups():
    body = '<style>.g { stroke: red }</style><g class="g"><rect width="5" height="5" stroke="inherit"/></g>'
    assert _style(body).stroke == "#ff0000"


def test_unsupported_css_rules_are_reported():
    sheet = "<style>g rect::before { fill: red } @media print { rect { fill: blue } }</style>"
    notes = _notes(sheet + '<rect width="5" height="5"/>')
    assert notes == ["2 CSS rules were not applied"]


def test_groups_become_groups_with_their_own_opacity():
    (group,) = _shapes('<g opacity="0.5"><rect width="5" height="5" style="opacity: 50%"/></g>')
    assert isinstance(group, GroupShape) and group.opacity == 0.5
    assert group.children[0].style.opacity == 0.5
    assert _notes('<g opacity="0.5"><rect width="5" height="5"/><rect width="5" height="5"/></g>') == []


def test_links_and_nested_groups_become_groups_and_empty_ones_vanish():
    (link,) = _shapes('<a href="#x"><g><rect width="5" height="5"/></g><g/><g><title>Empty</title></g></a>')
    assert isinstance(link, GroupShape) and len(link.children) == 1
    assert isinstance(link.children[0], GroupShape)
    assert _shapes("<g><g/></g>") == []


def test_layer_opacity_over_several_shapes_is_still_approximated():
    body = '<g inkscape:groupmode="layer" opacity="0.5"><rect width="5" height="5"/><rect width="5" height="5"/></g>'
    document, notes = read_svg_with_notes(_svg(body))
    assert [shape.style.opacity for shape in document.layers[0].shapes] == [0.5, 0.5]
    assert notes == ["1 transparent group was approximated by making each object in it transparent"]


def test_sublayers_become_groups_in_their_layer():
    body = '<g inkscape:groupmode="layer"><g inkscape:groupmode="layer"><rect width="5" height="5"/></g></g>'
    document = read_svg(_svg(body))
    assert len(document.layers) == 1 and isinstance(document.layers[0].shapes[0], GroupShape)


def test_group_transforms_go_to_the_shapes():
    (group,) = _shapes('<g transform="translate(10 20)"><rect width="5" height="5"/></g>')
    assert group.transform == (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    assert (group.children[0].x, group.children[0].y) == (10, 20)


def test_very_deep_nesting_is_cut_off_with_a_note():
    shapes, notes = read_shapes_svg(_svg("<g>" * 40 + '<rect width="5" height="5"/>' + "</g>" * 40))
    assert shapes == [] and notes == ["1 other element was left out"]


def test_visibility_hidden_skips_shapes_and_visible_brings_them_back():
    body = '<g visibility="hidden"><rect width="5" height="5"/><rect visibility="visible" width="6" height="6"/></g>'
    shapes = leaves(_shapes(body))
    assert [shape.width for shape in shapes] == [6]


# --- paint and stroke values ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "fill, opacity",
    [("rgba(255, 0, 0, 0.5)", 0.502), ("#ff000080", 0.502), ("#f008", 0.533), ("hsla(0, 100%, 50%, 0.25)", 0.251)],
)
def test_colour_alpha_becomes_paint_opacity(fill, opacity):
    style = _style(f'<rect width="5" height="5" fill="{fill}" fill-opacity="0.5"/>')
    assert style.fill == "#ff0000"
    assert style.fill_opacity == pytest.approx(opacity * 0.5, abs=1e-3)


def test_gradient_fallback_colour_is_used():
    assert _style('<rect width="5" height="5" fill="url(#missing) #00ff00"/>').fill == "#00ff00"
    assert _style('<rect width="5" height="5" fill="url(#missing)"/>').fill is None


def test_pattern_paint_is_grey_unless_a_fallback_is_named():
    pattern = '<pattern id="p" width="2" height="2"/>'
    assert _style(pattern + '<rect width="5" height="5" fill="url(#p)"/>').fill == "#808080"
    assert _style(pattern + '<rect width="5" height="5" fill="url(#p) #00ff00"/>').fill == "#00ff00"


def test_stroke_options_are_read_and_scaled_with_the_transform():
    style = _style(
        '<path d="M0 0 L10 0" transform="scale(2)" stroke="black" stroke-width="1" stroke-linecap="square" '
        'stroke-linejoin="bevel" stroke-miterlimit="7" stroke-dasharray="1 2 3" stroke-dashoffset="1"/>'
    )
    assert (style.cap, style.join, style.miter_limit) == ("square", "bevel", 7)
    assert style.dashes == (2, 4, 6, 2, 4, 6)
    assert (style.stroke_width, style.dash_offset) == (2, 2)


@pytest.mark.parametrize("dasharray", ["none", "1 -2", "0 0", "1 x"])
def test_invalid_dash_lists_are_solid(dasharray):
    assert _style(f'<path d="M0 0 L1 1" stroke="black" stroke-dasharray="{dasharray}"/>').dashes == ()


def test_unknown_stroke_values_fall_back_to_defaults():
    style = _style('<path d="M0 0 L1 1" stroke-linecap="pointy" stroke-linejoin="miter-clip" stroke-miterlimit="x"/>')
    assert (style.cap, style.join, style.miter_limit) == ("butt", "miter", 4)


# --- rounded rectangles --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "radii, expected", [('rx="3"', (3, 3)), ('ry="4"', (4, 4)), ('rx="3" ry="4"', (3, 4)), ('rx="-1"', (0, 0))]
)
def test_rect_radii_follow_the_svg_rules(radii, expected):
    (rect,) = _shapes(f'<rect width="20" height="20" {radii}/>')
    assert (rect.rx, rect.ry) == expected


def test_rect_radii_scale_with_the_element_transform():
    (rect,) = _shapes('<rect width="20" height="20" rx="2" transform="scale(2 3)"/>')
    assert (rect.width, rect.height, rect.rx, rect.ry) == pytest.approx((40, 60, 4, 6))


# --- use and symbol ------------------------------------------------------------------------------


def test_use_copies_the_target_at_x_y_with_its_own_transform():
    body = '<defs><rect id="r" width="5" height="5"/></defs><use href="#r" x="10" y="20" transform="translate(1 1)"/>'
    (rect,) = _shapes(body)
    assert (rect.x, rect.y) == (11, 21)


def test_use_can_reference_forward_and_anything_drawn():
    shapes = _shapes('<use xlink:href="#later" x="100"/><circle id="later" r="5"/>')
    assert [(type(shape), shape.cx) for shape in shapes] == [(EllipseShape, 100), (EllipseShape, 0)]


def test_use_style_is_inherited_but_the_target_style_wins():
    body = '<defs><path id="p" d="M0 0 L1 1" stroke="red"/></defs><use href="#p" fill="blue" stroke="green"/>'
    style = _style(body)
    assert (style.fill, style.stroke) == ("#0000ff", "#ff0000")


def test_symbol_viewbox_is_fitted_and_centred():
    body = (
        '<symbol id="s" viewBox="0 0 10 10"><rect width="10" height="10"/></symbol>'
        '<use href="#s" x="5" width="40" height="20"/>'
    )
    (group,) = _shapes(body)
    assert isinstance(group, GroupShape)
    (rect,) = group.children
    assert (rect.x, rect.y, rect.width, rect.height) == (15, 0, 20, 20)


def test_symbol_with_aspect_ratio_none_stretches():
    body = (
        '<symbol id="s" viewBox="0 0 10 10" preserveAspectRatio="none"><rect width="10" height="10"/></symbol>'
        '<use href="#s" width="40" height="20"/>'
    )
    (rect,) = leaves(_shapes(body))
    assert (rect.width, rect.height) == (40, 20)


# --- nested viewports -----------------------------------------------------------------------------


def _nested(body: str):
    return leaves(_shapes(body))


def test_nested_svg_is_translated_by_x_and_y():
    (rect,) = _nested('<svg x="10" y="20" width="50" height="50"><rect width="5" height="5"/></svg>')
    assert (rect.x, rect.y, rect.width, rect.height) == (10, 20, 5, 5)


def test_nested_svg_view_box_scales_and_centres():
    body = '<svg x="5" width="40" height="20" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
    (rect,) = _nested(body)
    assert (rect.x, rect.y, rect.width, rect.height) == (15, 0, 20, 20)


def test_nested_svg_slice_and_none():
    inner = '<rect width="10" height="10"/>'
    slice_svg = f'<svg width="40" height="20" viewBox="0 0 10 10" preserveAspectRatio="xMinYMin slice">{inner}</svg>'
    (sliced,) = _nested(slice_svg)
    assert (sliced.x, sliced.y, sliced.width, sliced.height) == (0, 0, 40, 40)
    none_svg = f'<svg width="40" height="20" viewBox="0 0 10 10" preserveAspectRatio="none">{inner}</svg>'
    (stretched,) = _nested(none_svg)
    assert (stretched.width, stretched.height) == (40, 20)


def test_nested_svg_inside_nested_svg_composes():
    body = (
        '<svg x="10" y="10" width="80" height="80"><svg x="5" y="5" width="20" height="20" viewBox="0 0 10 10">'
        '<rect width="10" height="10"/></svg></svg>'
    )
    (rect,) = _nested(body)
    assert (rect.x, rect.y, rect.width, rect.height) == (15, 15, 20, 20)


def test_percentages_inside_a_nested_viewport_use_that_viewport():
    body = '<svg width="40" height="20"><rect width="50%" height="50%"/></svg>'
    (rect,) = _nested(body)
    assert (rect.width, rect.height) == (20, 10)


def test_nested_svg_without_size_fills_the_parent_viewport():
    (rect,) = _nested('<svg><rect width="100%" height="100%"/></svg>')
    assert (rect.width, rect.height) == (100, 100)


def test_nested_svg_transform_applies_before_the_viewport():
    (rect,) = _nested('<svg transform="translate(7 0)" width="50" height="50"><rect width="5" height="5"/></svg>')
    assert rect.x == 7


def test_nested_svg_without_extent_draws_nothing():
    for attributes in ('width="0" height="10"', 'width="10" height="-1"', 'width="10" height="10" viewBox="0 0 0 5"'):
        assert _shapes(f"<svg {attributes}><rect width='5' height='5'/></svg>") == []


def test_invalid_view_box_and_aspect_are_ignored_and_counted():
    body = '<svg width="20" height="20" viewBox="1 2 3" preserveAspectRatio="bogus"><rect width="5" height="5"/></svg>'
    assert [rect.width for rect in _nested(body)] == [5]
    assert _notes(body) == ["2 invalid values were ignored"]


def test_nested_svg_keeps_opacity_conditions_and_display():
    (group,) = _shapes('<svg width="50" height="50" opacity="0.5"><rect width="5" height="5"/></svg>')
    assert isinstance(group, GroupShape) and group.opacity == 0.5
    assert _shapes('<svg width="50" height="50" systemLanguage="xx"><rect width="5" height="5"/></svg>') == []
    (hidden,) = _shapes('<svg width="50" height="50" display="none"><rect width="5" height="5"/></svg>')
    assert hidden.hidden


def test_use_of_svg_takes_its_size_from_the_use():
    body = (
        '<defs><svg id="s" viewBox="0 0 10 10"><rect width="10" height="10"/></svg></defs>'
        '<use href="#s" x="5" width="40" height="20"/>'
    )
    (rect,) = _nested(body)
    assert (rect.x, rect.y, rect.width, rect.height) == (15, 0, 20, 20)


def test_extreme_viewport_values_never_raise():
    body = '<svg width="1e308in" height="1e308in" viewBox="0 0 1e-300 1e-300"><rect width="5" height="5"/></svg>'
    _shapes(body)


@pytest.mark.parametrize(
    ("body", "noted"),
    [
        ('<svg width="10" height="10"><rect width="5" height="5"/></svg>', False),
        ('<svg width="10" height="10"><rect x="8" width="5" height="5"/></svg>', True),
        ('<svg width="10" height="10" overflow="visible"><rect x="8" width="5" height="5"/></svg>', False),
        ('<svg width="10" height="10" overflow="auto"><rect x="8" width="5" height="5"/></svg>', False),
        (
            '<svg width="10" height="10" viewBox="0 0 10 10" preserveAspectRatio="xMidYMid slice">'
            '<rect width="5" height="5"/></svg>',
            False,
        ),
        (
            '<svg width="20" height="10" viewBox="0 0 10 10" preserveAspectRatio="xMidYMid slice">'
            '<rect width="10" height="10"/></svg>',
            True,
        ),
        ('<symbol id="s" width="10" height="10"><rect x="8" width="5" height="5"/></symbol><use href="#s"/>', True),
    ],
)
def test_viewport_overflow_is_noted_not_clipped(body, noted):
    messages = _notes(body)
    clipped = [m for m in messages if "viewport" in m]
    assert bool(clipped) == noted


def test_overflowing_content_is_kept():
    body = '<svg width="10" height="10"><rect x="8" width="50" height="5"/></svg>'
    (rect,) = _nested(body)
    assert rect.width == 50


def test_definitions_are_only_drawn_where_used():
    body = (
        '<defs><rect id="a" width="1" height="1"/></defs><symbol id="b"><rect width="2" height="2"/></symbol>'
        '<clipPath id="c"><rect width="3" height="3"/></clipPath>'
    )
    assert _shapes(body) == []


def test_missing_and_cyclic_references_are_noted():
    body = '<use href="#nothing"/><use href="nothing"/><g id="a"><use href="#b"/></g><g id="b"><use href="#a"/></g>'
    shapes, notes = read_shapes_svg(_svg(body))
    assert shapes == []
    assert notes == [
        "2 references to missing elements were left out",
        "2 references that refer to themselves were left out",
    ]


def test_deep_use_chains_stop():
    chain = "".join(f'<g id="g{index}"><use href="#g{index + 1}"/></g>' for index in range(40))
    _shapes(f"<defs>{chain}<rect id='g40' width='1' height='1'/></defs><use href='#g0'/>")


# --- text ----------------------------------------------------------------------------------------


def test_tspan_lines_become_text_objects():
    body = (
        '<text x="10" y="20" font-size="10"><tspan x="10" y="20">One</tspan>'
        '<tspan x="10" dy="1.5em" fill="red">Two</tspan><tspan dy="2">Three</tspan></text>'
    )
    texts = _shapes(body)
    assert [(text.text, text.x, text.y) for text in texts] == [("One", 10, 20), ("Two", 10, 35), ("Three", 10, 37)]
    assert texts[1].style.fill == "#ff0000"


def test_unpositioned_tspans_continue_the_line_and_mixed_styles_are_noted():
    shapes, notes = read_shapes_svg(_svg('<text x="1" y="2">Hello <tspan font-weight="bold">big</tspan> world</text>'))
    assert [text.text for text in shapes] == ["Hello big world"]
    assert notes == []
    shapes, notes = read_shapes_svg(_svg('<text x="1" y="2">Hello <tspan fill="red">red</tspan></text>'))
    assert notes == ["1 text line with mixed styles now uses one style"]


def test_text_whitespace_from_indented_files_collapses():
    (text,) = _shapes('<text x="0" y="10">\n    Hello\n    world\n  </text>')
    assert text.text == "Hello world"


def test_text_anchor_is_kept():
    (text,) = _shapes('<text x="50" y="10" style="text-anchor: middle">Mid</text>')
    assert (text.anchor, text.x) == ("middle", 50)


# --- notes ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, note",
    [
        ('<rect width="5" height="5" clip-path="url(#c)"/>', "1 clip path was ignored, its content is shown unclipped"),
        ('<g mask="url(#m)"><rect width="5" height="5"/></g>', "1 mask was ignored, its content is shown unmasked"),
        ('<image href="a.png" width="5" height="5"/>', "1 image was left out: its file was not found"),
        ('<rect width="5" height="5" style="filter:url(#f)"/>', "1 filter effect (blur, shadow, …) was left out"),
        ('<path d="M0 0 L1 1" marker-end="url(#m)"/>', "1 line with markers (arrowheads) lost them"),
        ('<foreignObject width="5" height="5"/>', "1 other element was left out"),
        (
            '<pattern id="g" width="2" height="2"/><rect width="5" height="5" fill="url(#g)"/>'
            '<rect width="5" height="5" stroke="url(#g)"/>',
            "2 patterns were painted grey",
        ),
    ],
)
def test_lost_features_are_noted(body, note):
    assert _notes(body) == [note]


def test_metadata_and_editor_elements_make_no_notes():
    body = (
        "<title>T</title><desc>D</desc><metadata><x/></metadata><script>1</script>"
        '<sodipodi:namedview xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd"/>'
        '<g inkscape:groupmode="layer"><rect width="5" height="5"/></g>'
    )
    document, notes = read_svg_with_notes(_svg(body))
    assert notes == []
    assert [layer.name for layer in document.layers] == ["Layer 1"]


def test_garbage_values_never_break_the_import():
    body = (
        '<style>}}} .a { fill: </style><rect class="a" width="x" height="5" rx="y" opacity="?" '
        'style="fill-opacity: lots; stroke-dasharray: ,,,; stroke-width: -"/><use href="#"/><text>   </text>'
    )
    read_svg_with_notes(_svg(body))


# --- round trip and speed ------------------------------------------------------------------------


def test_every_new_property_round_trips_through_svg():
    style = Style(
        fill="#123456",
        stroke="#654321",
        stroke_width=3,
        opacity=0.5,
        fill_opacity=0.25,
        stroke_opacity=0.75,
        fill_rule="evenodd",
        cap="round",
        join="bevel",
        miter_limit=8,
        dashes=(4, 2),
        dash_offset=1,
    )
    shapes = [
        RectShape(1, 0, 0, 10, 10, style, rx=2, ry=3),
        PathShape(2, (MoveTo(0, 0), LineTo(5, 5)), style),
        TextShape(3, 5, 6, "Hi", 12, style, anchor="end"),
    ]
    document = Document(100, 100, [Layer("L", True, shapes)], next_id=4)
    assert read_svg(write_svg(document)) == document


def test_large_files_import_in_reasonable_time():
    rects = "".join(f'<rect class="c{index % 300}" x="{index}" width="5" height="5"/>' for index in range(10_000))
    sheet = "<style>" + "".join(f".c{index} {{ fill: #{index:06x} }}" for index in range(300)) + "</style>"
    start = time.perf_counter()
    shapes = _shapes(sheet + rects)
    assert len(shapes) == 10_000
    assert time.perf_counter() - start < 3.0


# --- real-world style fixtures -------------------------------------------------------------------


def _fixture(name: str):
    return read_svg_with_notes((SAMPLES / name).read_text(encoding="utf-8"))


def test_illustrator_export_with_css_classes():
    document, notes = _fixture("illustrator_classes.svg")
    assert notes == []
    group, text = document.layers[0].shapes
    assert isinstance(group, GroupShape)
    rect, path, circle, line = group.children
    assert rect.style.fill == "#e30613"
    assert (path.style.fill, path.style.stroke, path.style.cap, path.style.join) == (None, "#1d1d1b", "round", "round")
    assert (circle.style.fill, circle.style.opacity) == ("#009fe3", 0.5)
    assert line.style.dashes == (4, 2)
    assert (text.text, text.x, text.y, text.font_size, text.style.fill) == ("Hello", 10, 90, 12, "#1d1d1b")


def test_inkscape_drawing_with_layers_and_text_lines():
    document, notes = _fixture("inkscape_layers_text.svg")
    scale = units.to_px(1, "mm", 96)
    assert [(layer.name, layer.visible) for layer in document.layers] == [
        ("Background", True),
        ("Text", True),
        ("Effects", False),
    ]
    rect, ring = document.layers[0].shapes
    assert (rect.rx, rect.ry) == pytest.approx((3 * scale, 3 * scale))
    assert ring.style.fill_rule == "evenodd"
    first, second, label, below = document.layers[1].shapes
    assert [text.text for text in (first, second, label, below)] == ["First line", "Second line", "Label", "below"]
    assert (first.anchor, second.y - first.y) == ("middle", pytest.approx(10 * scale))
    assert below.y - label.y == pytest.approx(12 * scale)
    transparent, arrow = document.layers[2].shapes
    assert isinstance(transparent, GroupShape) and transparent.opacity == 0.5
    assert [shape.style.opacity for shape in transparent.children] == [1.0, 1.0]
    assert arrow.style.opacity == 1.0
    assert notes == ["1 line with markers (arrowheads) lost them"]


def test_figma_frame_export():
    document, notes = _fixture("figma_frame.svg")
    (clipped,) = document.layers[0].shapes
    assert clipped.masking.type == "clip"
    inner, clip_rect = clipped.children
    assert clipped.masking.mask_ids == (clip_rect.id,)
    assert (clip_rect.width, clip_rect.height) == (120, 80)
    assert isinstance(inner, GroupShape)
    background, ring, card, circle, translucent, gradient = inner.children
    assert background.style.fill == "#ffffff"
    assert ring.style.fill_rule == "evenodd"
    assert (card.rx, card.style.fill_opacity) == (8, 0.25)
    assert (circle.style.fill, circle.style.stroke_opacity) == (None, 0.5)
    assert translucent.style.fill_opacity == pytest.approx(0.5, abs=0.01)
    assert gradient.style.fill == LinearGradient(
        60, 72, 110, 77, (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff")), units="userSpaceOnUse"
    )
    assert notes == []


def test_icon_sprite_with_symbols_and_uses():
    document, notes = _fixture("icon_sprite.svg")
    red_icon, green_icon, pair = document.layers[0].shapes
    assert all(isinstance(shape, GroupShape) for shape in (red_icon, green_icon, pair))
    (red,), (green,), (left_dot, right_dot) = red_icon.children, green_icon.children, pair.children
    assert (red.x, red.y, red.width, red.style.fill) == (2, 2, 16, "#ff0000")
    assert (green.x, green.width, green.style.fill) == (42, 16, "#00ff00")
    assert [left_dot.segments[0], right_dot.segments[0]] == [MoveTo(80, 30), MoveTo(84, 30)]
    assert left_dot.style.fill == "#0000ff"
    assert notes == [
        "1 reference to a missing element was left out",
        "1 reference that refers to itself was left out",
    ]


def test_groups_are_written_as_g_and_read_back():
    inner = GroupShape(3, (TextShape(4, 0, 20, "Hi", 12, Style()),), opacity=0.25)
    group = GroupShape(1, (RectShape(2, 0, 0, 10, 10, Style()), inner), opacity=0.5)
    document = Document(100, 100, [Layer("L", True, [group, RectShape(5, 50, 0, 5, 5, Style())])], next_id=6)
    svg = write_svg(document)
    assert '<g opacity="0.5">' in svg and '<g opacity="0.25">' in svg
    reread = read_svg(svg)
    assert reread == document


def test_inkscape_guides_and_grid_open_in_document_px():
    document, notes = _fixture("inkscape_guides_grid.svg")
    scale = units.to_px(1, "mm", 96)
    vertical, horizontal = document.guides
    assert (vertical.orientation, vertical.position) == ("vertical", pytest.approx(20 * scale))
    assert (horizontal.orientation, horizontal.position) == ("horizontal", pytest.approx(30 * scale))
    assert document.grid.spacing == pytest.approx(5 * scale) and document.grid.major_every == 2
    assert notes == ["1 angled guide was left out"]
    ids = [shape.id for layer in document.layers for shape in layer.shapes] + [guide.id for guide in document.guides]
    assert len(ids) == len(set(ids)) and document.next_id > max(ids)


def test_guides_and_grid_round_trip_through_svg():
    document = Document(
        100,
        80,
        [Layer("L", True, [RectShape(1, 0, 0, 5, 5, Style())])],
        next_id=4,
        guides=(Guide(2, "horizontal", 12.5), Guide(3, "vertical", 70)),
        grid=GridSettings(4, 4),
    )
    svg = write_svg(document)
    assert "sodipodi:guide" in svg and 'position="0,67.5"' in svg and "inkscape:grid" in svg
    assert read_svg(svg) == document


def test_documents_without_guides_write_no_namedview():
    assert "namedview" not in write_svg(Document(100, 80, [Layer("L", True, [])]))


def test_grid_spacing_with_a_unit_and_broken_grids():
    def grid_of(spacing):
        svg = _svg(
            '<sodipodi:namedview xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd">'
            f'<inkscape:grid type="xygrid" spacingx="{spacing}" empspacing="4"/></sodipodi:namedview>',
            'width="100" height="100" viewBox="0 0 100 100"',
        )
        return read_svg_with_notes(svg)

    document, notes = grid_of("0.5in")
    assert document.grid.spacing == pytest.approx(48) and notes == []
    document, notes = grid_of("lots")
    assert document.grid is None and notes == ["1 grid setting couldn't be read, the default grid is used"]


def test_pasting_ignores_guides():
    shapes, notes = read_shapes_svg((SAMPLES / "inkscape_guides_grid.svg").read_text(encoding="utf-8"))
    assert notes == [] and len(shapes) == 1


def test_a_broken_path_among_valid_shapes_opens_with_its_valid_part_and_a_note():
    body = (
        '<path d="M 10 10 L 20 20"/><path d="M 0 0 L 50 0 L 50"/><path d="L 1 1"/>'
        '<polyline points="0,0 10,10 20"/><rect width="5" height="5"/>'
    )
    document, notes = read_svg_with_notes(_svg(body))
    shapes = leaves(document.layers[0].shapes)
    assert len(shapes) == 4
    assert shapes[1].segments == (MoveTo(0, 0), LineTo(50, 0))
    assert notes == ["3 paths had errors and were cut short"]


def test_percentages_resolve_against_the_view_box_per_axis():
    svg = _svg('<rect x="10%" y="10%" width="50%" height="50%"/>', 'viewBox="0 0 200 100"')
    (rect,) = read_shapes_svg(svg)[0]
    assert (rect.x, rect.y, rect.width, rect.height) == (20, 10, 100, 50)


def test_units_in_geometry_and_stroke_width():
    shapes = _shapes('<rect x="1in" width="2.54cm" height="12pt" stroke="red" stroke-width="1mm"/>')
    rect = shapes[0]
    assert (rect.x, rect.width, rect.height) == (96, pytest.approx(96), pytest.approx(16))
    assert rect.style.stroke_width == pytest.approx(96 / 25.4)


def test_em_lengths_chain_through_nested_groups():
    body = '<g font-size="10"><g font-size="2em"><text x="1em" y="2em">Hi</text></g></g>'
    (text,) = leaves(_shapes(body))
    assert text.font_size == 20 and (text.x, text.y) == (20, 40)


def test_percent_font_size_is_relative_to_the_parent():
    (text,) = leaves(_shapes('<g font-size="20"><text font-size="50%" x="1em" y="0">Hi</text></g>'))
    assert text.font_size == 10 and text.x == 10


def test_ex_is_half_the_font_size():
    (text,) = _shapes('<text font-size="20" x="2ex" y="0">Hi</text>')
    assert text.x == 20


def test_invalid_geometry_attribute_is_counted_and_defaulted():
    document, notes = read_svg_with_notes(_svg('<rect x="10PX" width="5" height="5"/>'))
    assert leaves(document.layers[0].shapes)[0].x == 0
    assert notes == ["1 invalid value was ignored"]


def test_relative_dy_in_em_still_spaces_lines():
    shapes = _shapes('<text font-size="10" x="0" y="10"><tspan x="0" dy="1.5em">Next</tspan></text>')
    assert shapes[0].y == 25


def test_current_color_follows_the_elements_own_color_svg2_style():
    body = (
        '<g color="red" fill="currentColor"><rect width="5" height="5"/>'
        '<g color="blue"><rect width="5" height="5"/></g></g>'
    )
    first, second = leaves(_shapes(body))
    assert (first.style.fill, second.style.fill) == ("#ff0000", "#0000ff")


def test_color_inherit_and_current_color_take_the_parents_colour():
    body = (
        '<g color="green"><rect color="inherit" fill="currentColor" width="5" height="5"/>'
        '<rect color="currentColor" fill="currentColor" width="5" height="5"/></g>'
    )
    assert [shape.style.fill for shape in leaves(_shapes(body))] == ["#008000", "#008000"]


def test_current_color_alpha_multiplies_like_other_colours():
    (rect,) = leaves(
        _shapes('<rect color="rgba(0,0,255,.5)" fill="currentColor" fill-opacity=".5" width="5" height="5"/>')
    )
    assert rect.style.fill == "#0000ff"
    assert rect.style.fill_opacity == pytest.approx(0.25, abs=0.01)


def test_attribute_units_are_case_sensitive_but_css_ones_are_not():
    (attribute,) = leaves(_shapes('<rect stroke="red" stroke-width="10PX" width="5" height="5"/>'))
    (styled,) = leaves(_shapes('<rect stroke="red" style="stroke-width: 20PX" width="5" height="5"/>'))
    assert attribute.style.stroke_width == 1
    assert styled.style.stroke_width == 20


def test_invalid_values_are_ignored_and_counted_and_the_lower_layer_survives():
    body = '<rect fill="red" style="fill: nonsense; stroke: ActiveBorder" width="5" height="5"/>'
    document, notes = read_svg_with_notes(_svg(body))
    (rect,) = leaves(document.layers[0].shapes)
    assert rect.style.fill == "#ff0000" and rect.style.stroke is None
    assert notes == ["2 invalid values were ignored"]


def test_a_realistic_exported_sheet_with_combinators():
    sheet = (
        "<style>svg g.icon path{fill:#111} g.icon > path.accent{fill:#e00} "
        "path:first-child{stroke:#00f} .a + .b{opacity:.5} @media screen{rect{fill:#0a0}}</style>"
    )
    body = (
        sheet + '<g class="icon"><path class="accent" d="M0 0 L5 5"/><path d="M0 0 L9 9"/></g>'
        '<path d="M0 0 L7 7"/><rect width="5" height="5"/>'
    )
    group, loose_path, rect = _shapes(body)
    first, second = leaves([group])
    assert (first.style.fill, first.style.stroke) == ("#ee0000", "#0000ff")
    assert (second.style.fill, second.style.stroke) == ("#111111", None)
    assert loose_path.style.fill == "#000000"
    assert rect.style.fill == "#00aa00"


def test_style_elements_with_other_type_or_media_are_not_read():
    body = (
        '<style type="text/foo">rect{fill:red}</style><style media="print">rect{fill:green}</style>'
        '<style type="TEXT/CSS" media="screen, print">rect{stroke:blue}</style>'
        '<rect width="5" height="5"/>'
    )
    document, notes = read_svg_with_notes(_svg(body))
    (rect,) = leaves(document.layers[0].shapes)
    assert (rect.style.fill, rect.style.stroke) == ("#000000", "#0000ff")
    assert notes == ["2 CSS rules were not applied"]


_MULTILINGUAL = (
    '<switch><text systemLanguage="de" x="0" y="10">Hallo</text><text systemLanguage="en" x="0" y="10">Hello</text>'
    '<text x="0" y="10">Hi</text></switch>'
)


def _texts(body: str, languages: tuple[str, ...]) -> tuple[list[str], list[str]]:
    shapes, notes = read_shapes_svg(_svg(body), languages)
    return [shape.text for shape in leaves(shapes)], notes


def test_switch_draws_only_the_choice_for_the_users_language():
    assert _texts(_MULTILINGUAL, ("de", "en")) == (
        ["Hallo"],
        ["2 elements meant for another language or viewer were left out"],
    )
    assert _texts(_MULTILINGUAL, ("en",))[0] == ["Hello"]
    assert _texts(_MULTILINGUAL, ("fr", "en"))[0] == ["Hello"]
    assert _texts(_MULTILINGUAL, ("fr",))[0] == ["Hi"]


def test_conditions_outside_a_switch_hide_elements():
    body = '<text systemLanguage="de" x="0" y="10">Hallo</text><text x="0" y="30">Always</text>'
    assert _texts(body, ("en",)) == (["Always"], ["1 element meant for another language or viewer was left out"])
    assert _texts(body, ("de",))[0] == ["Hallo", "Always"]


def test_required_extensions_false_and_features_ignored():
    body = '<rect requiredExtensions="x" width="5" height="5"/><rect requiredFeatures="y" width="6" height="6"/>'
    assert [shape.width for shape in leaves(_shapes(body))] == [6]


def test_illustrator_switch_falls_back_to_the_plain_content():
    body = (
        '<switch><foreignObject requiredExtensions="http://ns.adobe.com/AdobeIllustrator/10.0/"><x/></foreignObject>'
        '<g><rect width="5" height="5"/></g></switch>'
    )
    assert len(leaves(_shapes(body))) == 1


def test_system_language_on_a_use_target_and_symbol_content():
    body = (
        '<defs><rect id="d" systemLanguage="de" width="5" height="5"/>'
        '<symbol id="s"><rect systemLanguage="de" width="5" height="5"/><rect width="7" height="7"/></symbol></defs>'
        '<use href="#d"/><use href="#s"/>'
    )
    assert [shape.width for shape in leaves(read_shapes_svg(_svg(body), ("en",))[0])] == [7]
    assert len(leaves(read_shapes_svg(_svg(body), ("de",))[0])) == 3


def test_a_layer_for_another_language_is_left_out():
    body = (
        '<g inkscape:groupmode="layer" systemLanguage="de"><rect width="5" height="5"/></g>'
        '<g inkscape:groupmode="layer"><rect width="6" height="6"/></g>'
    )
    document, _notes_ = read_svg_with_notes(_svg(body), ("en",))
    assert len(document.layers) == 1


def test_text_whitespace_default_and_preserve_modes():
    texts = [
        shape.text
        for shape in leaves(
            _shapes(
                '<text x="0" y="10">  a \n   b\t c  </text>'
                '<text x="0" y="20" xml:space="preserve">  a  b </text>'
                '<g xml:space="preserve"><text x="0" y="30">  inherited </text></g>'
            )
        )
    ]
    assert texts == ["a b c", "  a  b ", "  inherited "]


def test_xml_space_changes_per_tspan_without_losing_boundary_spaces():
    body = '<text x="0" y="10">one <tspan xml:space="preserve"> two  </tspan> <tspan xml:space="default"> three </tspan></text>'
    (text,) = leaves(_shapes(body))
    assert text.text == "one  two   three"


def test_spaces_survive_saving_and_reopening():
    shape = TextShape(1, 0, 10, "  two  spaces ", 16, Style())
    svg = write_svg(Document(layers=[Layer("L", shapes=[shape])]))
    assert 'xml:space="preserve"' in svg
    (reopened,) = leaves(read_svg(svg).layers[0].shapes)
    assert reopened.text == "  two  spaces "


def test_text_without_special_spaces_is_written_without_xml_space():
    shape = TextShape(1, 0, 10, "plain text", 16, Style())
    assert "xml:space" not in write_svg(Document(layers=[Layer("L", shapes=[shape])]))


def test_clipboard_svg_keeps_spaces():
    from presstoshape.formats.svg import write_shapes_svg

    shape = TextShape(1, 0, 10, " lead", 16, Style())
    (back,) = leaves(read_shapes_svg(write_shapes_svg([shape], (0, 0, 50, 50)))[0])
    assert back.text == " lead"


UNEVEN = "1 stroke under uneven scaling was approximated"
SKEW = "1 skewed text lost its skew"


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ('<path d="M0 0 L9 9" stroke="red" transform="scale(8,2)"/>', [UNEVEN]),
        ('<path d="M0 0 L9 9" transform="scale(8,2)"/>', []),
        ('<path d="M0 0 L9 9" stroke="red" transform="scale(3)"/>', []),
        ('<path d="M0 0 L9 9" stroke="red" transform="scale(-1,1)"/>', []),
        ('<path d="M0 0 L9 9" stroke="red" transform="rotate(30) scale(2)"/>', []),
        ('<path d="M0 0 L9 9" stroke="red" transform="skewX(20)"/>', [UNEVEN]),
        ('<text x="0" y="10" transform="skewX(20)">Hi</text>', [SKEW]),
        ('<text x="0" y="10" transform="rotate(20)">Hi</text>', []),
        ('<text x="0" y="10" transform="scale(2) translate(5,5)">Hi</text>', []),
    ],
)
def test_approximations_under_transforms_are_noted(body, expected):
    assert _notes(body) == expected


# --- root viewport ------------------------------------------------------------------------------------


def _root_rect(attrs: str):
    document, notes = read_svg_with_notes(_svg('<rect width="100" height="100"/>', attrs))
    (rect,) = leaves(document.layers[0].shapes)
    return document, rect, notes


def test_root_with_other_proportions_keeps_its_size_and_centres_the_content():
    document, rect, _ = _root_rect('width="200" height="100" viewBox="0 0 100 100"')
    assert (document.width, document.height) == (200, 100)
    assert (rect.x, rect.y, rect.width, rect.height) == (50, 0, 100, 100)


def test_root_aspect_none_stretches_and_slice_covers():
    _, stretched, _ = _root_rect('width="200" height="100" viewBox="0 0 100 100" preserveAspectRatio="none"')
    assert (stretched.x, stretched.width, stretched.height) == (0, 200, 100)
    _, sliced, _ = _root_rect('width="200" height="100" viewBox="0 0 100 100" preserveAspectRatio="xMinYMin slice"')
    assert (sliced.x, sliced.y, sliced.width, sliced.height) == (0, 0, 200, 200)


def test_root_with_the_same_proportions_or_percentages_is_unchanged():
    document, rect, _ = _root_rect('width="200" height="200" viewBox="0 0 100 100"')
    assert (document.width, document.height, rect.width) == (100, 100, 100)
    document, rect, _ = _root_rect('width="100%" height="50%" viewBox="0 0 100 100"')
    assert (document.width, document.height, rect.width) == (100, 100, 100)


def test_root_preserve_aspect_ratio_is_ignored_without_a_view_box():
    document, rect, _ = _root_rect('width="200" height="100" preserveAspectRatio="none"')
    assert (document.width, document.height, rect.x, rect.width) == (200, 100, 0, 100)


def test_root_in_physical_units_keeps_the_unit():
    document, _, _ = _root_rect('width="50mm" height="25mm" viewBox="0 0 100 100"')
    assert document.unit == "mm"
    assert document.width == pytest.approx(50 / 25.4 * 96)


def test_invalid_root_aspect_ratio_is_counted():
    _, _, notes = _root_rect('width="200" height="100" viewBox="0 0 100 100" preserveAspectRatio="centre"')
    assert notes == ["1 invalid value was ignored"]


def test_own_files_are_never_fitted():
    document = Document(layers=[Layer("a", shapes=[RectShape(1, 0, 0, 10, 10, Style())])], next_id=2)
    document.width, document.height, document.unit = 960.0, 480.0, "in"
    first = write_svg(document)
    reopened = read_svg(first)
    assert write_svg(reopened) == first
