import xml.etree.ElementTree as ET

from presstoshape.formats.svg import write_shapes_svg, write_svg
from presstoshape.formats.svg_paint import PaintDefs
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.layout import Guide
from presstoshape.models.shapes import (
    CompositeShape,
    EllipseShape,
    GradientStop,
    LinearGradient,
    RadialGradient,
    RectShape,
    Style,
)

NS = {"s": "http://www.w3.org/2000/svg"}
STOPS = (GradientStop(0, "#ff0000"), GradientStop(0.5, "#00ff00", 0.5), GradientStop(1, "#0000ff"))
LINEAR = LinearGradient(0, 0, 1, 0, STOPS)
RADIAL = RadialGradient(0.5, 0.5, 0.5, 0.25, 0.5, STOPS[::2], "userSpaceOnUse", "reflect", (1, 0, 0, 2, 5, 0))


def _doc(*shapes) -> Document:
    return Document(100, 100, [Layer("L", True, list(shapes))])


def _root(doc: Document) -> ET.Element:
    return ET.fromstring(write_svg(doc).split("\n", 1)[1])


def test_colours_and_none_are_written_as_before():
    defs = PaintDefs()
    assert (defs.attribute("#123456"), defs.attribute(None)) == ("#123456", "none")
    assert defs.element() is None


def test_gradient_is_written_once_in_defs_and_referenced():
    root = _root(_doc(RectShape(1, 0, 0, 10, 10, Style(fill=LINEAR, stroke=RADIAL))))
    assert root[0].tag.endswith("defs")
    linear, radial = root[0]
    rect = root.find(".//s:rect", NS)
    assert rect.get("fill") == f"url(#{linear.get('id')})"
    assert rect.get("stroke") == f"url(#{radial.get('id')})"
    assert linear.tag.endswith("linearGradient") and radial.tag.endswith("radialGradient")


def test_equal_gradients_share_one_element():
    shapes = [RectShape(i, 0, 0, 10, 10, Style(fill=LinearGradient(0, 0, 1, 0, STOPS))) for i in (1, 2, 3)]
    root = _root(_doc(*shapes))
    assert len(root.findall(".//s:linearGradient", NS)) == 1
    assert len({rect.get("fill") for rect in root.iter("{http://www.w3.org/2000/svg}rect")}) == 1


def test_ids_are_unique_and_stable_between_saves():
    doc = _doc(
        RectShape(1, 0, 0, 10, 10, Style(fill=LINEAR, stroke=RADIAL)), EllipseShape(2, 5, 5, 4, 4, Style(fill=RADIAL))
    )
    first = write_svg(doc)
    assert first == write_svg(doc)
    ids = [gradient.get("id") for gradient in _root(doc)[0]]
    assert ids == ["grad1", "grad2"]


def test_defaults_are_left_out_and_values_written_when_set():
    root = _root(_doc(RectShape(1, 0, 0, 10, 10, Style(fill=LINEAR, stroke=RADIAL))))
    linear, radial = root[0]
    assert set(linear.attrib) == {"id", "x1", "y1", "x2", "y2"}
    assert radial.get("gradientUnits") == "userSpaceOnUse"
    assert radial.get("spreadMethod") == "reflect"
    assert radial.get("gradientTransform") == "matrix(1 0 0 2 5 0)"
    assert (radial.get("fx"), radial.get("cx")) == ("0.25", "0.5")


def test_stops_carry_offset_colour_and_opacity_only_when_below_one():
    linear = _root(_doc(RectShape(1, 0, 0, 10, 10, Style(fill=LINEAR))))[0][0]
    stops = [dict(stop.attrib) for stop in linear]
    assert stops == [
        {"offset": "0", "stop-color": "#ff0000"},
        {"offset": "0.5", "stop-color": "#00ff00", "stop-opacity": "0.5"},
        {"offset": "1", "stop-color": "#0000ff"},
    ]


def test_defs_come_before_the_layers_and_after_the_namedview():
    doc = _doc(RectShape(1, 0, 0, 10, 10, Style(fill=LINEAR)))
    doc.guides = [Guide(5, "vertical", 10.0)]
    tags = [child.tag.rsplit("}", 1)[1] for child in _root(doc)]
    assert tags.index("defs") < tags.index("g") and tags[0] == "namedview"


def test_files_without_gradients_have_no_defs():
    assert "<defs" not in write_svg(_doc(RectShape(1, 0, 0, 10, 10, Style())))


def test_composite_parts_register_their_gradients():
    part = RectShape(2, 0, 0, 10, 10, Style(fill=LINEAR))
    composite = CompositeShape(1, (part,), ("add",), Style(fill=RADIAL))
    root = _root(_doc(composite))
    assert len(root[0]) == 2


def test_clipboard_svg_has_defs():
    text = write_shapes_svg([RectShape(1, 0, 0, 10, 10, Style(fill=LINEAR))], (0.0, 0.0, 10.0, 10.0))
    assert "<linearGradient" in text and 'fill="url(#grad1)"' in text
