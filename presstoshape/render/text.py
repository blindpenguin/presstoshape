"""Text outlines shared by canvas drawing, export, hit-testing and bounds, so they can't disagree."""

from functools import cache

import skia

from presstoshape.models.shapes import TextShape

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


_ANCHOR_SHARE = {"start": 0.0, "middle": 0.5, "end": 1.0}


def anchor_offset(shape: TextShape) -> float:
    """How far the line starts left of (x, y): none for start, half its advance for middle, all for end."""
    share = _ANCHOR_SHARE.get(shape.anchor, 0.0)
    if share == 0.0 or not shape.text or shape.font_size <= 0:
        return 0.0
    return -share * _font(shape.font_size).measureText(shape.text)


def text_blob(shape: TextShape) -> skia.TextBlob | None:
    """Same glyphs and layout as `text_path`, for drawing through Skia's glyph cache."""
    if not shape.text or shape.font_size <= 0:
        return None
    return skia.TextBlob.MakeFromText(shape.text, _font(shape.font_size))


def text_path(shape: TextShape) -> skia.Path:
    """Glyph outlines at `font_size`, baseline through (x, y), placed by the anchor."""
    path = skia.Path()
    if not shape.text or shape.font_size <= 0:
        return path
    font = _font(shape.font_size)
    glyphs = font.textToGlyphs(shape.text)
    origin = skia.Point(shape.x + anchor_offset(shape), shape.y)
    for glyph, pos in zip(glyphs, font.getPos(glyphs, origin)):
        path.addPath(font.getPath(glyph), pos.x(), pos.y())
    path.setFillType(skia.PathFillType.kWinding)
    return path
