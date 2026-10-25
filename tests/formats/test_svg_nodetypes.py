from dataclasses import replace

from presstoshape.formats.svg import read_svg, write_svg
from presstoshape.formats.svg_nodetypes import node_types, with_node_types
from presstoshape.geometry.segments import ellipse_segments
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import Close, CubicTo, LineTo, MoveTo, PathShape, Style

ELLIPSE = ellipse_segments(0, 0, 10, 5)
SMOOTH = (MoveTo(0, 0), CubicTo(0, 10, 10, 10, 20, 0), CubicTo(30, -10, 40, -10, 50, 0))
# What Inkscape writes for this path: "M 0,0 C 10,-10 20,-10 30,0 C 40,10 50,10 60,0 L 30,40 Z" with
# sodipodi:nodetypes="cccc" + "c" (four nodes, the closed subpath's first one repeated).
INKSCAPE = (MoveTo(0, 0), CubicTo(10, -10, 20, -10, 30, 0), CubicTo(40, 10, 50, 10, 60, 0), LineTo(30, 40), Close())
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:sodipodi="http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd" '
    'width="100" height="100"><path d="M 0,0 C 10,-10 20,-10 30,0 C 40,10 50,10 60,0 L 30,40 Z" '
    'sodipodi:nodetypes="{}"/></svg>'
)


def _cornered(segments, index):
    out = list(segments)
    out[index] = replace(out[index], corner=True)
    return tuple(out)


def _corners(segments):
    return [i for i, s in enumerate(segments) if getattr(s, "corner", False)]


def test_nothing_written_without_corner_nodes():
    assert node_types(SMOOTH) is None
    assert node_types(ELLIPSE) is None


def test_letters_per_node_with_closed_start_repeated():
    assert node_types(_cornered(SMOOTH, 1)) == "ccc"
    assert node_types(_cornered(ELLIPSE, 0)) == "czzzc"
    longer_out = (*SMOOTH[:2], replace(SMOOTH[2], c1x=40, c1y=-20, corner=True))
    assert node_types(longer_out) == "csc"


def test_corner_read_only_where_handles_line_up():
    assert _corners(with_node_types(INKSCAPE, "ccccc")) == [1]
    assert _corners(with_node_types(INKSCAPE, "czccc")) == []


def test_closed_start_type_comes_from_the_repeated_letter():
    assert _corners(with_node_types(ELLIPSE, "szzzc")) == [0]
    assert _corners(with_node_types(ELLIPSE, "czzzs")) == []


def test_types_for_other_path_data_are_ignored():
    assert with_node_types(INKSCAPE, "cccc") == INKSCAPE
    assert with_node_types(INKSCAPE, "") == INKSCAPE


def test_inkscape_file_opens_with_corner_nodes():
    path = read_svg(SVG.format("ccccc")).layers[0].shapes[0]
    assert _corners(path.segments) == [1]
    assert _corners(read_svg(SVG.format("cscc")).layers[0].shapes[0].segments) == []


def test_corner_nodes_round_trip_through_svg():
    shapes = [PathShape(1, _cornered(_cornered(ELLIPSE, 0), 2), Style()), PathShape(2, _cornered(SMOOTH, 1), Style())]
    document = Document(100, 100, [Layer("L", shapes=shapes)])
    text = write_svg(document)
    assert 'sodipodi:nodetypes="czczc"' in text
    read = read_svg(text).layers[0].shapes
    assert [_corners(shape.segments) for shape in read] == [[0, 2], [1]]
