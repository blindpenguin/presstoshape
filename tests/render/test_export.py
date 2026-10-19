import struct
import zlib

import skia

from presstoshape.editing.operations import documents, shapes
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import RectShape, Style
from presstoshape.render.export import MAX_SIDE, export_size, render_png


def _doc() -> Document:
    return Document(100, 50, [Layer("L", True, [RectShape(1, 10, 10, 20, 20, Style(fill="#ff0000", stroke=None))])])


def _decode(data: bytes) -> skia.Image:
    return skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data))


def _rgba(image: skia.Image, x: int, y: int) -> tuple[int, ...]:
    return tuple(int(v) for v in image.toarray(colorType=skia.kRGBA_8888_ColorType)[y, x])


def test_export_size_scales_and_rounds_up():
    assert export_size(_doc(), 1) == (100, 50)
    assert export_size(_doc(), 2) == (200, 100)
    assert export_size(_doc(), 0.333) == (34, 17)


def test_png_has_scaled_size_transparent_background_and_content():
    image = _decode(render_png(_doc(), 2))
    assert (image.width(), image.height()) == (200, 100)
    assert _rgba(image, 0, 0) == (0, 0, 0, 0)
    assert _rgba(image, 40, 40) == (255, 0, 0, 255)


def test_hidden_layers_are_not_exported():
    doc = _doc()
    doc.layers[0].visible = False
    assert _rgba(_decode(render_png(doc, 1)), 20, 20) == (0, 0, 0, 0)


def test_oversized_export_is_rejected():
    assert render_png(_doc(), MAX_SIDE) is None


def test_export_operation_writes_file_without_touching_undo(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (50, 50))
    session.state.dirty = False
    undo_depth = session.undo_count
    calls = []
    session.subscribe(lambda: calls.append(1))
    target = tmp_path / "out.png"
    assert documents.export_png(session, str(target), 1.5)
    assert _decode(target.read_bytes()).width() == 900
    assert session.state.export.scale == 1.5
    assert session.state.status_message == "Exported out.png (900 × 600 px)"
    assert not session.state.dirty
    assert session.undo_count == undo_depth
    assert calls == [1]


def test_export_operation_failure_reports_status(tmp_path):
    session = Session()
    assert not documents.export_png(session, str(tmp_path / "missing" / "out.png"), 1)
    assert session.state.status_message.startswith("Export failed")


def _chunks(png: bytes) -> list[tuple[bytes, bytes]]:
    chunks, position = [], 8
    while position < len(png):
        (length,) = struct.unpack(">I", png[position : position + 4])
        kind, data = png[position + 4 : position + 8], png[position + 8 : position + 8 + length]
        (crc,) = struct.unpack(">I", png[position + 8 + length : position + 12 + length])
        assert crc == zlib.crc32(kind + data)
        chunks.append((kind, data))
        position += 12 + length
    return chunks


def test_dpi_is_recorded_in_a_valid_phys_chunk():
    png = render_png(_doc(), 2, dpi=300)
    chunks = _chunks(png)
    assert [kind for kind, _data in chunks[:2]] == [b"IHDR", b"pHYs"]
    assert struct.unpack(">IIB", chunks[1][1]) == (11811, 11811, 1)
    assert _decode(png).width() == 2 * _doc().width


def test_without_dpi_no_phys_chunk():
    assert b"pHYs" not in [kind for kind, _data in _chunks(render_png(_doc(), 1))]
