import xml.etree.ElementTree as ET

import pytest

from presstoshape.formats.svg import read_svg, write_svg
from presstoshape.geometry import affine, transforms
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import (
    Close,
    CubicTo,
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)


def _svg(body: str, attrs: str = 'width="100" height="50"') -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" {attrs}>{body}</svg>'
    )


def test_roundtrip_preserves_layers_shapes_and_styles():
    style = Style(fill="#ff0000", stroke=None, stroke_width=3.5)
    doc = Document(
        width=320,
        height=200,
        layers=[
            Layer(
                "Back",
                shapes=[
                    RectShape(1, 10, 20, 30, 40, style),
                    EllipseShape(2, 50, 60, 5, 7, Style()),
                ],
            ),
            Layer(
                "Hidden",
                visible=False,
                shapes=[
                    PathShape(3, (MoveTo(0, 0), CubicTo(1, 2, 3, 4, 5, 6), LineTo(7, 8), Close()), style),
                    TextShape(4, 5, 50, "Hello <&>", 24, Style(fill="#000000", stroke=None)),
                ],
            ),
        ],
        next_id=5,
    )
    loaded = read_svg(write_svg(doc))
    assert loaded == doc


def test_hidden_layer_content_is_kept():
    doc = read_svg(_svg('<g inkscape:groupmode="layer" style="display:none"><rect width="5" height="5"/></g>'))
    assert not doc.layers[0].visible
    assert len(doc.layers[0].shapes) == 1


def test_loose_elements_go_into_layers_around_real_ones():
    doc = read_svg(
        _svg(
            '<rect width="1" height="1"/>'
            '<g inkscape:groupmode="layer" inkscape:label="L"><circle r="2"/></g>'
            '<rect width="1" height="1"/>'
        )
    )
    assert [layer.name for layer in doc.layers] == ["Layer 1", "L", "Layer 3"]


def test_inherited_and_inline_styles():
    doc = read_svg(
        _svg('<g fill="red" stroke="blue"><rect width="5" height="5" style="stroke: none; stroke-width: 4"/></g>')
    )
    assert doc.layers[0].shapes[0].style == Style(fill="#ff0000", stroke=None, stroke_width=4)


def test_svg_defaults_black_fill_no_stroke():
    doc = read_svg(_svg('<rect width="5" height="5"/>'))
    assert doc.layers[0].shapes[0].style == Style(fill="#000000", stroke=None, stroke_width=1)


def test_translate_and_rotation_keep_primitive():
    doc = read_svg(
        _svg(
            '<g transform="translate(10 20)"><rect x="1" y="2" width="5" height="5"/></g>'
            '<rect width="5" height="5" transform="rotate(90)"/>'
        )
    )
    moved, rotated = doc.layers[0].shapes
    assert isinstance(moved, RectShape) and (moved.x, moved.y) == (11, 22)
    assert isinstance(rotated, RectShape)
    first = transforms.outline(rotated)[1]
    assert (first.x, first.y) == pytest.approx((0, 5))
    assert transforms.rotation_of(rotated) == pytest.approx(90)


def test_scale_transform_scales_stroke_width():
    doc = read_svg(_svg('<g transform="scale(2)"><line x2="5" stroke="black" stroke-width="3"/></g>'))
    assert doc.layers[0].shapes[0].style.stroke_width == 6


def test_viewbox_defines_document_size_and_origin():
    doc = read_svg(_svg('<rect x="10" y="10" width="5" height="5"/>', 'width="10cm" viewBox="10 10 80 40"'))
    assert (doc.width, doc.height) == (80, 40)
    assert (doc.layers[0].shapes[0].x, doc.layers[0].shapes[0].y) == (0, 0)


def test_path_arcs_and_quads_become_cubics():
    doc = read_svg(_svg('<path d="M0 0 Q 10 10 20 0 A 5 5 0 0 1 30 0 Z"/>'))
    segment_types = {type(s) for s in doc.layers[0].shapes[0].segments}
    assert segment_types == {MoveTo, CubicTo, Close}


def test_display_none_element_skipped_and_unsupported_skipped():
    doc = read_svg(_svg('<defs><rect width="5" height="5"/></defs><rect width="5" height="5" display="none"/>'))
    assert doc.layers[0].shapes == []


def test_ids_are_unique_and_next_id_follows():
    doc = read_svg(_svg('<rect width="1" height="1"/><circle r="1"/><polygon points="0,0 1,0 1,1"/>'))
    assert [s.id for s in doc.layers[0].shapes] == [1, 2, 3]
    assert doc.next_id == 4


def test_rejects_non_svg():
    with pytest.raises(ValueError):
        read_svg("<html/>")
    with pytest.raises(ET.ParseError):
        read_svg("<svg")


def _round_trip(*shapes):
    doc = Document(100, 100, [Layer("L", shapes=list(shapes))])
    return read_svg(write_svg(doc)).layers[0].shapes


def test_rotated_shapes_round_trip_as_same_types():
    rect = transforms.with_rotation(RectShape(1, 10, 20, 30, 40, Style()), 30)
    ellipse = transforms.with_rotation(EllipseShape(2, 50, 60, 5, 7, Style()), -45)
    text = transforms.with_rotation(TextShape(3, 5, 80, "Hi", 12.0, Style()), 15)
    for before, after in zip((rect, ellipse, text), _round_trip(rect, ellipse, text)):
        assert type(after) is type(before)
        assert after.transform == pytest.approx(before.transform, abs=1e-6)
        assert transforms.rotation_of(after) == pytest.approx(transforms.rotation_of(before))


def test_rotation_written_as_rotate():
    rect = transforms.with_rotation(RectShape(1, 10, 20, 30, 40, Style()), 30)
    svg = write_svg(Document(100, 100, [Layer("L", shapes=[rect])]))
    assert 'transform="rotate(30 25 40)"' in svg


def test_skew_written_as_matrix_and_round_trips():
    rect = RectShape(1, 0, 0, 10, 10, Style(), (1.0, 0.0, 0.5, 1.0, 2.0, 3.0))
    svg = write_svg(Document(100, 100, [Layer("L", shapes=[rect])]))
    assert 'transform="matrix(1 0 0.5 1 2 3)"' in svg
    (after,) = _round_trip(rect)
    assert isinstance(after, RectShape) and after.transform == pytest.approx(rect.transform)


def test_untransformed_shapes_write_no_transform():
    svg = write_svg(Document(100, 100, [Layer("L", shapes=[RectShape(1, 0, 0, 10, 10, Style())])]))
    assert "transform" not in svg


def test_inkscape_style_transforms_import_as_primitives():
    doc = read_svg(
        _svg(
            '<circle cx="10" cy="10" r="5" transform="matrix(0 1 -1 0 30 0)"/>'
            '<rect width="10" height="4" transform="scale(2 3)"/>'
            '<text x="5" y="10" font-size="10" transform="rotate(45 5 10)">Hi</text>'
        )
    )
    circle, rect, text = doc.layers[0].shapes
    assert isinstance(circle, EllipseShape) and (circle.cx, circle.cy) == pytest.approx((20, 10))
    assert isinstance(rect, RectShape) and (rect.width, rect.height) == pytest.approx((20, 12))
    assert rect.transform == affine.IDENTITY
    assert isinstance(text, TextShape) and (text.x, text.y) == pytest.approx((5, 10))
    assert transforms.rotation_of(text) == pytest.approx(45)
