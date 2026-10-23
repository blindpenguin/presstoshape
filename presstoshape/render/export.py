"""Raster export of the artboard, drawn by the same code as the canvas."""

import math
import struct
import zlib

import skia

from presstoshape.models.app_state import Document
from presstoshape.render.paths import PathCache
from presstoshape.render.scene import draw_document

MAX_SIDE = 16384
_INCHES_PER_METRE = 1 / 0.0254
# PNG signature (8 bytes) plus the IHDR chunk (length, type, 13 data bytes, CRC); pHYs must follow it.
_AFTER_IHDR = 8 + 4 + 4 + 13 + 4


def export_size(doc: Document, scale: float) -> tuple[int, int]:
    return max(1, math.ceil(doc.width * scale)), max(1, math.ceil(doc.height * scale))


def with_dpi(png: bytes, dpi: float) -> bytes:
    """The PNG with a pHYs chunk, so other programs know its physical size."""
    pixels_per_metre = round(dpi * _INCHES_PER_METRE)
    body = b"pHYs" + struct.pack(">IIB", pixels_per_metre, pixels_per_metre, 1)
    chunk = struct.pack(">I", 9) + body + struct.pack(">I", zlib.crc32(body))
    return png[:_AFTER_IHDR] + chunk + png[_AFTER_IHDR:]


def render_png(doc: Document, scale: float, dpi: float | None = None) -> bytes | None:
    """Visible layers on a transparent background, with `dpi` recorded when given; None if the size is out of
    range or encoding fails."""
    width, height = export_size(doc, scale)
    if scale <= 0 or max(width, height) > MAX_SIDE:
        return None
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(scale, scale)
    draw_document(canvas, doc, PathCache(), references=False)
    data = surface.makeImageSnapshot().encodeToData(skia.EncodedImageFormat.kPNG, 100)
    if data is None:
        return None
    return with_dpi(bytes(data), dpi) if dpi is not None else bytes(data)
