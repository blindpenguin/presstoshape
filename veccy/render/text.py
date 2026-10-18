"""Text outlines shared by canvas drawing, export, hit-testing and bounds, so they can't disagree."""

from functools import cache

import skia

from veccy.models.shapes import TextShape

# Matches the font-family written to SVG by svg_io.
FAMILY = "sans-serif"


@cache
def typeface() -> skia.Typeface:
    return skia.FontMgr().matchFamilyStyle(FAMILY, skia.FontStyle()) or skia.Typeface.MakeDefault()


def _font(size: float) -> skia.Font:
    font = skia.Font(typeface(), size)
    # Unhinted, subpixel-positioned outlines scale exactly with zoom.
    font.setHinting(skia.FontHinting.kNone)
    font.setSubpixel(True)
    font.setLinearMetrics(True)
    return font


def text_blob(shape: TextShape) -> skia.TextBlob | None:
    """Same glyphs and layout as `text_path`, for drawing through Skia's glyph cache."""
    if not shape.text or shape.font_size <= 0:
        return None
    return skia.TextBlob.MakeFromText(shape.text, _font(shape.font_size))


def text_path(shape: TextShape) -> skia.Path:
    """Glyph outlines at `font_size`, baseline starting at (x, y)."""
    path = skia.Path()
    if not shape.text or shape.font_size <= 0:
        return path
    font = _font(shape.font_size)
    glyphs = font.textToGlyphs(shape.text)
    for glyph, pos in zip(glyphs, font.getPos(glyphs, skia.Point(shape.x, shape.y))):
        path.addPath(font.getPath(glyph), pos.x(), pos.y())
    path.setFillType(skia.PathFillType.kWinding)
    return path
