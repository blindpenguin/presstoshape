import xml.etree.ElementTree as ET
from dataclasses import replace

from presstoshape.formats.clipboard import decode_shapes, encode_shapes
from presstoshape.formats.svg import read_svg, write_svg
from presstoshape.geometry import corners
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import Close, LineTo, MoveTo, PathShape, Rounding, Style

LIVE = PathShape(
    1,
    (
        MoveTo(0, 0),
        LineTo(100, 0, rounding=Rounding(10)),
        LineTo(100, 100, corner=True, rounding=Rounding(20, "chamfer")),
        LineTo(0, 100),
        Close(),
    ),
    Style(),
)


def _write(*shapes) -> str:
    return write_svg(Document(200, 200, [Layer("L", shapes=list(shapes))]))


def test_d_is_the_rounded_outline_and_metadata_keeps_the_rest():
    text = _write(LIVE)
    root = ET.fromstring(text)
    path = next(el for el in root.iter() if el.tag.endswith("}path"))
    assert path.get("d").count("C") == 1
    assert "nodetypes" not in text
    assert "presstoshape:corners" in text and 'roundings="1:round:10 2:chamfer:20"' in text


def test_live_corners_round_trip():
    (path,) = read_svg(_write(LIVE)).layers[0].shapes
    assert path.segments == LIVE.segments


def test_a_path_edited_elsewhere_opens_as_drawn():
    text = _write(LIVE).replace('d="M 0 0', 'd="M 1 0', 1)
    (path,) = read_svg(text).layers[0].shapes
    assert not corners.has_rounding(path.segments)
    assert (path.segments[0].x, path.segments[0].y) == (1, 0)


def test_element_transform_scales_the_radii():
    text = _write(LIVE)
    text = text.replace("<path ", '<path transform="scale(2)" ', 1)
    (path,) = read_svg(text).layers[0].shapes
    assert path.segments[1].rounding == Rounding(20)
    assert (path.segments[2].x, path.segments[2].y) == (200, 200)


def test_unreadable_metadata_gives_the_drawn_path():
    text = _write(LIVE).replace('roundings="1:round:10', 'roundings="1:wavy:10', 1)
    (path,) = read_svg(text).layers[0].shapes
    assert not corners.has_rounding(path.segments)
    assert [type(s) for s in path.segments] == [type(s) for s in corners.rounded(LIVE.segments)]


def test_plain_paths_get_no_metadata():
    plain = replace(
        LIVE, segments=tuple(replace(s, rounding=None) if hasattr(s, "rounding") else s for s in LIVE.segments)
    )
    assert "presstoshape:corners" not in _write(plain)


def test_live_corners_survive_the_clipboard():
    assert decode_shapes(encode_shapes([LIVE])) == [LIVE]
