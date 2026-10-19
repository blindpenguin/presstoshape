from PySide6.QtCore import QByteArray, QMimeData

from presstoshape.editing.operations.clipboard import ClipboardContent
from presstoshape.formats.clipboard import MIME_TYPE
from presstoshape.views import clipboard
from presstoshape.views.clipboard import SVG_TYPES, from_mime, offers_paste, to_mime

SVG = '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg"><rect width="1" height="1"/></svg>'


def _text(text: str) -> QMimeData:
    mime = QMimeData()
    mime.setText(text)
    return mime


def test_content_survives_the_mime_round_trip():
    content = ClipboardContent(b'{"format": "presstoshape-shapes"}', SVG)
    mime = to_mime(content)
    assert from_mime(mime) == (content.native, content.svg)
    assert all(mime.hasFormat(svg_type) for svg_type in SVG_TYPES)
    assert mime.text() == SVG


def test_svg_from_plain_text_is_accepted_other_text_is_not():
    assert from_mime(_text("  " + SVG)) == (None, "  " + SVG)
    assert from_mime(_text("<svg>")) == (None, "<svg>")
    assert from_mime(_text("hello")) == (None, None)
    assert from_mime(_text("<?xml version='1.0'?><html/>")) == (None, None)


def test_oversized_data_is_left_out(monkeypatch):
    monkeypatch.setattr(clipboard, "MAX_BYTES", 4)
    mime = to_mime(ClipboardContent(b"12345", SVG))
    assert from_mime(mime) == (None, None)


def test_paste_is_offered_for_shapes_svg_or_any_text():
    assert not offers_paste(None)
    assert not offers_paste(QMimeData())
    image_only = QMimeData()
    image_only.setData("image/png", QByteArray(b"\x89PNG"))
    assert not offers_paste(image_only)
    native = QMimeData()
    native.setData(MIME_TYPE, QByteArray(b"{}"))
    assert offers_paste(native)
    assert offers_paste(_text("anything"))
