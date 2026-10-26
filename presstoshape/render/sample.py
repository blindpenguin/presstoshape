"""The colour the document shows at a point (the eyedropper's Shift+click), drawn by the same code as the canvas."""

import skia

from presstoshape.geometry.boxes import Point
from presstoshape.geometry.colours import rgb_to_hex
from presstoshape.models.app_state import Document
from presstoshape.render.paths import PathCache
from presstoshape.render.scene import draw_document, parse_color


def color_at(
    doc: Document, cache: PathCache, point: Point, zoom: float, references: bool, page_color: str
) -> str | None:
    """`#rrggbb` of the page and shapes under `point` at `zoom` (handles, guides and grid left out); None where
    nothing is drawn (the pasteboard)."""
    surface = skia.Surface(1, 1)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    x, y = point
    # The point lands on the pixel's centre, as on screen.
    canvas.translate(0.5, 0.5)
    canvas.scale(zoom, zoom)
    canvas.translate(-x, -y)
    canvas.drawRect(skia.Rect.MakeWH(doc.width, doc.height), skia.Paint(Color=parse_color(page_color)))
    with cache.drawing(zoom, references):
        draw_document(canvas, doc, cache, references=references)
    pixels = surface.makeImageSnapshot().toarray(
        colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType
    )
    r, g, b, a = (int(channel) for channel in pixels[0][0])
    return rgb_to_hex((r, g, b)) if a else None
