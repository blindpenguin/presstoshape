"""Reading SVG from other programs: cascade, new style properties, <use>/<symbol>, text lines and notes."""

import time
from pathlib import Path

import pytest

from presstoshape.formats.svg import read_shapes_svg, read_svg, read_svg_with_notes, write_svg
from presstoshape.geometry import units
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import EllipseShape, GroupShape, LineTo, MoveTo, PathShape, RectShape, Style, TextShape
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
    sheet = "<style>g rect { fill: red } @media print { rect { fill: blue } }</style>"
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
    assert _style('<rect width="5" height="5" fill="url(#missing)"/>').fill == "#808080"


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
        ('<image href="a.png" width="5" height="5"/>', "1 image was left out"),
        ('<rect width="5" height="5" style="filter:url(#f)"/>', "1 filter effect (blur, shadow, …) was left out"),
        ('<path d="M0 0 L1 1" marker-end="url(#m)"/>', "1 line with markers (arrowheads) lost them"),
        ('<svg x="5"><rect width="5" height="5"/></svg>', "1 embedded SVG document was left out"),
        ('<foreignObject width="5" height="5"/>', "1 other element was left out"),
        (
            '<rect width="5" height="5" fill="url(#g)"/><rect width="5" height="5" stroke="url(#g)"/>',
            "2 gradients or patterns were painted grey",
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
    (frame,) = document.layers[0].shapes
    assert isinstance(frame, GroupShape)
    background, ring, card, circle, translucent, gradient = frame.children
    assert background.style.fill == "#ffffff"
    assert ring.style.fill_rule == "evenodd"
    assert (card.rx, card.style.fill_opacity) == (8, 0.25)
    assert (circle.style.fill, circle.style.stroke_opacity) == (None, 0.5)
    assert translucent.style.fill_opacity == pytest.approx(0.5, abs=0.01)
    assert gradient.style.fill == "#808080"
    assert notes == [
        "1 gradient or pattern was painted grey",
        "1 clip path was ignored, its content is shown unclipped",
    ]


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
