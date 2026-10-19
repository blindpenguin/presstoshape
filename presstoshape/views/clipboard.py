"""The system clipboard: PressToShape's own shape data plus SVG for other apps (and as text, for text editors)."""

from PySide6.QtCore import QByteArray, QMimeData
from PySide6.QtGui import QGuiApplication

from presstoshape.editing.operations.clipboard import ClipboardContent
from presstoshape.formats.clipboard import MAX_BYTES, MIME_TYPE

# Inkscape offers and prefers its own type; other apps use the standard one.
SVG_TYPES = ("image/svg+xml", "image/x-inkscape-svg")


def to_mime(content: ClipboardContent) -> QMimeData:
    mime = QMimeData()
    mime.setData(MIME_TYPE, QByteArray(content.native))
    svg = content.svg.encode("utf-8")
    for svg_type in SVG_TYPES:
        mime.setData(svg_type, QByteArray(svg))
    mime.setText(content.svg)
    return mime


def _looks_like_svg(text: str) -> bool:
    start = text.lstrip()[:4096]
    return (start.startswith("<svg") or start.startswith("<?xml")) and "<svg" in start


def from_mime(mime: QMimeData) -> tuple[bytes | None, str | None]:
    """(native, svg) as offered; SVG may also come from plain text. Oversized data is left out."""
    native = None
    if mime.hasFormat(MIME_TYPE):
        data = mime.data(MIME_TYPE).data()
        native = data if len(data) <= MAX_BYTES else None
    svg = None
    for svg_type in SVG_TYPES:
        if mime.hasFormat(svg_type):
            data = mime.data(svg_type).data()
            if len(data) <= MAX_BYTES:
                svg = data.decode("utf-8", errors="replace")
                break
    if svg is None and mime.hasText():
        text = mime.text()
        if len(text) <= MAX_BYTES and _looks_like_svg(text):
            svg = text
    return native, svg


def offers_paste(mime: QMimeData | None) -> bool:
    """Only looks at the offered formats; whether the content is usable shows when pasting."""
    if mime is None:
        return False
    return mime.hasFormat(MIME_TYPE) or any(mime.hasFormat(svg_type) for svg_type in SVG_TYPES) or mime.hasText()


def put(content: ClipboardContent) -> None:
    QGuiApplication.clipboard().setMimeData(to_mime(content))


def read() -> tuple[bytes | None, str | None]:
    mime = QGuiApplication.clipboard().mimeData()
    return from_mime(mime) if mime is not None else (None, None)


def can_paste() -> bool:
    return offers_paste(QGuiApplication.clipboard().mimeData())
