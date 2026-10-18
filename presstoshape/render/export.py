"""Raster export of the artboard, drawn by the same code as the canvas."""

import math

import skia

from presstoshape.models.app_state import Document
from presstoshape.render.paths import PathCache
from presstoshape.render.scene import draw_document

MAX_SIDE = 16384


def export_size(doc: Document, scale: float) -> tuple[int, int]:
    return max(1, math.ceil(doc.width * scale)), max(1, math.ceil(doc.height * scale))


def render_png(doc: Document, scale: float) -> bytes | None:
    """Visible layers on a transparent background; None if the size is out of range or encoding fails."""
    width, height = export_size(doc, scale)
    if scale <= 0 or max(width, height) > MAX_SIDE:
        return None
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(scale, scale)
    draw_document(canvas, doc, PathCache())
    data = surface.makeImageSnapshot().encodeToData(skia.EncodedImageFormat.kPNG, 100)
    return bytes(data) if data is not None else None
