import base64
import os
import socket
import xml.etree.ElementTree as ET
from urllib.parse import quote_from_bytes

import pytest

from presstoshape.formats import svg_images, svg_reader
from presstoshape.formats.svg import read_shapes_svg, read_svg_with_notes
from presstoshape.formats.svg_images import ImageBudget
from presstoshape.models.shapes import Aspect, GroupShape, ImageShape, children_of
from tests.helpers import TINY_PNG, quadrant_picture, tiny_image

PICTURE = tiny_image()
B64 = base64.b64encode(TINY_PNG).decode()
DATA_URI = f"data:image/png;base64,{B64}"
NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'


def svg(body, attributes='width="100" height="100"'):
    return f"<svg {NS} {attributes}>{body}</svg>"


def read(body, base_folder=None, attributes='width="100" height="100"'):
    document, notes = read_svg_with_notes(svg(body, attributes), base_folder=base_folder)
    return [shape for layer in document.layers for shape in layer.shapes], notes


def flat(shapes):
    for shape in shapes:
        if isinstance(shape, ImageShape):
            yield shape
        yield from flat(children_of(shape))


def only(body, **kwargs):
    shapes, notes = read(body, **kwargs)
    (shape,) = flat(shapes)
    return shape, notes


def test_data_uri_with_base64_gives_the_picture():
    shape, notes = only(f'<image width="20" height="10" href="{DATA_URI}"/>')
    assert shape.data == PICTURE and shape.data.data == TINY_PNG
    assert (shape.x, shape.y, shape.width, shape.height) == (0, 0, 20, 10)
    assert notes == []


def test_xlink_href_is_read_and_href_wins():
    shape, _notes = only(f'<image width="2" height="2" xlink:href="{DATA_URI}"/>')
    assert shape.data == PICTURE
    other = quadrant_picture()
    second = "data:image/png;base64," + base64.b64encode(other.data).decode()
    shape, _notes = only(f'<image width="2" height="2" href="{second}" xlink:href="{DATA_URI}"/>')
    assert shape.data == other


@pytest.mark.parametrize(
    "uri",
    [
        f"data:image/png;base64,{B64[:30]}\n  {B64[30:]}",
        f"data:;base64,{B64}",
        f"data:image/png;charset=x;base64,{B64}",
        f"  {DATA_URI}  ",
        f"data:image/png;base64,{B64.rstrip('=')}",
        "data:image/png," + quote_from_bytes(TINY_PNG),
    ],
)
def test_data_uri_forms(uri):
    shape, notes = only(f'<image width="2" height="2" href="{uri}"/>')
    assert shape.data.data == TINY_PNG and notes == []


@pytest.mark.parametrize("uri", ["data:", "data:image/png;base64", "data:image/png;base64,@@@@", "data:image/png,junk"])
def test_broken_data_uris_are_counted_and_skipped(uri):
    shapes, notes = read(f'<image width="2" height="2" href="{uri}"/>')
    assert not list(flat(shapes))
    assert notes == ["1 image was left out: it is not a readable PNG, JPEG, WebP or GIF"]


def test_svg_images_are_refused_by_type_and_by_content(tmp_path):
    (tmp_path / "drawing.png").write_bytes(b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"/>')
    body = (
        '<image width="2" height="2" href="data:image/svg+xml;utf8,%3Csvg/%3E"/>'
        '<image width="2" height="2" href="drawing.png"/>'
    )
    shapes, notes = read(body, tmp_path)
    assert not list(flat(shapes))
    assert notes == ["2 images were left out: they are SVG drawings, which cannot be placed as pictures"]


def test_relative_absolute_and_file_urls(tmp_path):
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "a b.png").write_bytes(TINY_PNG)
    body = (
        '<image width="2" height="2" href="art/a%20b.png"/>'
        '<image width="2" height="2" href="./art/a b.png"/>'
        f'<image width="2" height="2" href="{tmp_path / "art" / "a b.png"}"/>'
        f'<image width="2" height="2" href="{(tmp_path / "art" / "a b.png").as_uri()}"/>'
    )
    shapes, notes = read(body, tmp_path)
    assert [shape.data.data for shape in flat(shapes)] == [TINY_PNG] * 4 and notes == []
    assert len({id(shape.data) for shape in flat(shapes)}) == 1


def test_relative_path_without_a_base_folder_is_missing():
    _shapes, notes = read('<image width="2" height="2" href="a.png"/>')
    assert notes == ["1 image was left out: its file was not found"]


def test_missing_file_and_directory_are_missing(tmp_path):
    (tmp_path / "folder.png").mkdir()
    shapes, notes = read(
        '<image width="2" height="2" href="nope.png"/><image width="2" height="2" href="folder.png"/>', tmp_path
    )
    assert not list(flat(shapes))
    assert notes == ["2 images were left out: their files were not found"]


@pytest.mark.parametrize(
    "href",
    [
        "http://example.com/a.png",
        "https://example.com/a.png",
        "ftp://example.com/a.png",
        "//example.com/a.png",
        "file://example.com/a.png",
        "gopher://x/y",
    ],
)
def test_remote_images_are_refused_without_touching_the_network(href, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    shapes, notes = read(f'<image width="2" height="2" href="{href}"/>')
    assert not list(flat(shapes))
    assert notes == ["1 image was left out: it is on the internet, which PressToShape does not fetch"]


def test_special_files_are_never_opened(tmp_path):
    fifo = tmp_path / "pipe.png"
    os.mkfifo(fifo)
    (tmp_path / "zero.png").symlink_to("/dev/zero")
    (tmp_path / "loop.png").symlink_to("loop.png")
    body = "".join(
        f'<image width="2" height="2" href="{href}"/>' for href in ("pipe.png", "zero.png", "loop.png", "/dev/zero")
    )
    shapes, notes = read(body, tmp_path)
    assert not list(flat(shapes))
    assert notes == ["4 images were left out: their files were not found"]


def test_a_symlink_to_a_picture_works(tmp_path):
    (tmp_path / "real.png").write_bytes(TINY_PNG)
    (tmp_path / "link.png").symlink_to("real.png")
    shape, _notes = only('<image width="2" height="2" href="link.png"/>', base_folder=tmp_path)
    assert shape.data.data == TINY_PNG


def test_ten_thousand_elements_with_one_data_uri_probe_it_once(monkeypatch):
    calls = []
    real = svg_images.probe
    monkeypatch.setattr(svg_images, "probe", lambda raw: calls.append(1) or real(raw))
    body = f'<image width="2" height="2" href="{DATA_URI}"/>' * 10_000
    shapes, notes = read(body)
    images = list(flat(shapes))
    assert len(images) == 10_000 and notes == []
    assert len(calls) == 1
    assert len({id(shape.data) for shape in images}) == 1


def test_a_file_referenced_many_times_is_read_once(tmp_path, monkeypatch):
    (tmp_path / "a.png").write_bytes(TINY_PNG)
    opened = []
    real = os.open
    monkeypatch.setattr(svg_images.os, "open", lambda *args, **kwargs: opened.append(args[0]) or real(*args, **kwargs))
    read('<image width="2" height="2" href="a.png"/>' * 2_000, tmp_path)
    assert len(opened) == 1


def test_an_oversize_data_uri_is_refused_before_decoding(monkeypatch):
    monkeypatch.setattr(svg_images, "_MAX_BASE64_CHARS", 100)
    decoded = []
    monkeypatch.setattr(svg_images.base64, "b64decode", lambda *args, **kwargs: decoded.append(1))
    shapes, notes = read(f'<image width="2" height="2" href="data:image/png;base64,{"A" * 5000}"/>')
    assert not list(flat(shapes)) and not decoded
    assert notes == ["1 image was left out: it is too large"]


def test_an_oversize_file_is_refused_by_size_before_reading(tmp_path, monkeypatch):
    (tmp_path / "big.png").write_bytes(TINY_PNG + b"\0" * 100)
    monkeypatch.setattr(svg_images, "MAX_BYTES", 50)
    reads = []
    real = os.read
    monkeypatch.setattr(svg_images.os, "read", lambda *args: reads.append(1) or real(*args))
    _shapes, notes = read('<image width="2" height="2" href="big.png"/>', tmp_path)
    assert notes == ["1 image was left out: it is too large"] and not reads


def test_pictures_over_the_pixel_limit_are_too_large():
    huge = bytearray(TINY_PNG)
    huge[16:24] = (20000).to_bytes(4, "big") * 2
    uri = "data:image/png;base64," + base64.b64encode(bytes(huge)).decode()
    _shapes, notes = read(f'<image width="2" height="2" href="{uri}"/>')
    assert notes == ["1 image was left out: it is too large"]


def test_the_import_budget_stops_embedding_more(monkeypatch):
    first, second = tiny_image(), quadrant_picture()
    monkeypatch.setattr(svg_reader, "ImageBudget", lambda: ImageBudget(remaining=len(first.data) + 10))
    other = "data:image/png;base64," + base64.b64encode(second.data).decode()
    body = f'<image width="2" height="2" href="{DATA_URI}"/><image width="2" height="2" href="{other}"/>' + (
        f'<image width="2" height="2" href="{DATA_URI}"/>'
    )
    shapes, notes = read(body)
    assert [shape.data.digest for shape in flat(shapes)] == [first.digest, first.digest]
    assert notes == ["1 image was left out: it is too large"]


def test_the_viewport_defaults_to_the_pixel_size_and_follows_one_given_side():
    shape, _notes = only(f'<image href="{DATA_URI}" x="3" y="4"/>')
    assert (shape.x, shape.y, shape.width, shape.height) == (3, 4, 2, 2)
    wide = quadrant_picture(60, 30)
    uri = "data:image/png;base64," + base64.b64encode(wide.data).decode()
    shape, _notes = only(f'<image href="{uri}" width="30"/>')
    assert (shape.width, shape.height) == (30, 15)
    shape, _notes = only(f'<image href="{uri}" height="30" width="auto"/>')
    assert (shape.width, shape.height) == (60, 30)


@pytest.mark.parametrize("size", ['width="0" height="5"', 'width="5" height="0"', 'width="-5" height="5"'])
def test_zero_or_negative_sizes_draw_nothing(size):
    shapes, notes = read(f'<image href="{DATA_URI}" {size}/>')
    assert not list(flat(shapes))


@pytest.mark.parametrize(
    "text, aspect",
    [
        (None, Aspect("xMidYMid")),
        ("none", Aspect("none")),
        ("xMinYMax", Aspect("xMinYMax")),
        ("xMaxYMin slice", Aspect("xMaxYMin", True)),
        ("defer xMidYMax meet", Aspect("xMidYMax")),
    ],
)
def test_preserve_aspect_ratio(text, aspect):
    attribute = "" if text is None else f'preserveAspectRatio="{text}"'
    shape, notes = only(f'<image width="9" height="5" href="{DATA_URI}" {attribute}/>')
    assert shape.aspect == aspect and notes == []


def test_an_invalid_aspect_value_is_noted_and_default():
    shape, notes = only(f'<image width="9" height="5" href="{DATA_URI}" preserveAspectRatio="middle"/>')
    assert shape.aspect == Aspect("xMidYMid")
    assert notes == ["1 invalid value was ignored"]


def test_transform_opacity_and_visibility():
    shape, _notes = only(f'<image width="10" height="10" href="{DATA_URI}" opacity="0.5" transform="rotate(90 5 5)"/>')
    assert shape.opacity == 0.5
    assert shape.transform != (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    shapes, _notes = read(f'<image width="10" height="10" href="{DATA_URI}" visibility="hidden"/>')
    assert not list(flat(shapes))
    shape, _notes = only(f'<image width="10" height="10" href="{DATA_URI}" style="display:none"/>')
    assert shape.hidden


def test_a_singular_transform_draws_nothing():
    shapes, _notes = read(f'<image width="10" height="10" href="{DATA_URI}" transform="scale(0 1)"/>')
    assert not list(flat(shapes))


def test_group_opacity_and_nesting():
    shapes, _notes = read(f'<g opacity="0.5"><image width="4" height="4" href="{DATA_URI}"/></g>')
    (group,) = shapes
    assert isinstance(group, GroupShape) and group.opacity == 0.5
    assert isinstance(group.children[0], ImageShape)


def test_symbol_use_switch_and_nested_svg():
    body = (
        f'<defs><symbol id="s" viewBox="0 0 2 2"><image width="2" height="2" href="{DATA_URI}"/></symbol></defs>'
        '<use href="#s" x="10" width="20" height="20"/>'
        f'<switch><image width="4" height="4" href="{DATA_URI}"/></switch>'
        f'<svg x="50" width="30" height="30"><image width="4" height="4" href="{DATA_URI}"/></svg>'
        f'<a href="#x"><image width="4" height="4" href="{DATA_URI}"/></a>'
    )
    shapes, notes = read(body)
    assert len(list(flat(shapes))) == 4 and notes == []


def test_clip_path_and_mask_wrap_the_image():
    body = (
        '<defs><clipPath id="c"><rect width="5" height="5"/></clipPath>'
        '<mask id="m"><rect width="5" height="5" fill="white"/></mask></defs>'
        f'<image width="10" height="10" href="{DATA_URI}" clip-path="url(#c)"/>'
        f'<image width="10" height="10" href="{DATA_URI}" mask="url(#m)"/>'
    )
    shapes, _notes = read(body)
    clip, mask = shapes
    assert clip.masking.type == "clip" and mask.masking.type == "luminance"
    assert len(list(flat(shapes))) == 2


def test_each_note_is_counted_once_per_kind(tmp_path):
    body = (
        '<image width="2" height="2" href="a.png"/><image width="2" height="2" href="b.png"/>'
        '<image width="2" height="2" href="http://x/y.png"/>'
        '<image width="2" height="2" href="data:image/svg+xml,x"/>'
        '<image width="2" height="2" href="data:image/png;base64,AAAA"/>'
    )
    _shapes, notes = read(body, tmp_path)
    assert notes == [
        "2 images were left out: their files were not found",
        "1 image was left out: it is not a readable PNG, JPEG, WebP or GIF",
        "1 image was left out: it is on the internet, which PressToShape does not fetch",
        "1 image was left out: it is an SVG drawing, which cannot be placed as a picture",
    ]


@pytest.mark.parametrize("href", ["", " ", "\x00", "file://", "data", "%", "a" * 100_000, "C:\\x\\y.png", "~/x.png"])
def test_odd_hrefs_never_raise(href, tmp_path):
    shapes, _notes = read(
        f'<image width="2" height="2" href="{quote_from_bytes(href.encode(), safe="/:~\\ ")}"/>', tmp_path
    )
    assert not list(flat(shapes))


def test_missing_href_is_missing():
    _shapes, notes = read('<image width="2" height="2"/>')
    assert notes == ["1 image was left out: its file was not found"]


def test_pasted_svg_reads_data_uris_and_not_relative_files():
    text = svg(f'<image width="2" height="2" href="{DATA_URI}"/><image width="2" height="2" href="a.png"/>')
    shapes, notes = read_shapes_svg(text)
    assert len(list(flat(shapes))) == 1
    assert notes == ["1 image was left out: its file was not found"]


def test_ids_follow_document_order_and_stay_unique():
    shapes, _notes = read(
        f'<rect width="1" height="1"/><image width="2" height="2" href="{DATA_URI}"/><rect width="1" height="1"/>'
    )
    ids = [shape.id for shape in shapes]
    assert ids == sorted(set(ids))


def test_reading_never_makes_a_malformed_document_valid_xml_error():
    with pytest.raises(ET.ParseError):
        read_svg_with_notes("<svg><image")


def test_a_symbol_that_stretches_a_letterboxed_picture_draws_what_the_svg_draws():
    wide = quadrant_picture(60, 30)
    uri = "data:image/png;base64," + base64.b64encode(wide.data).decode()
    body = (
        '<symbol id="s" viewBox="0 0 1000 1000" preserveAspectRatio="none">'
        f'<image width="1000" height="1000" href="{uri}"/></symbol>'
        '<use href="#s" width="240" height="150"/>'
    )
    shapes, _notes = read(body, attributes='width="240" height="150"')
    (image,) = flat(shapes)
    from presstoshape.geometry.aspect import visible_box

    left, top, width, height = visible_box(image)
    assert (left, width) == (pytest.approx(0.0), pytest.approx(240.0))
    assert (top, height) == (pytest.approx(37.5), pytest.approx(75.0))


def test_xml_base_moves_where_relative_files_are_looked_for(tmp_path):
    (tmp_path / "pics").mkdir()
    (tmp_path / "pics" / "a.png").write_bytes(TINY_PNG)
    body = (
        '<image width="2" height="2" xml:base="pics/" href="a.png"/>'
        '<g xml:base="pics/"><image width="2" height="2" href="a.png"/></g>'
        '<image width="2" height="2" href="a.png"/>'
    )
    shapes, notes = read(body, tmp_path)
    assert len(list(flat(shapes))) == 2
    assert notes == ["1 image was left out: its file was not found"]
