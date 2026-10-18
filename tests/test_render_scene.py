import skia

from veccy.models.app_state import Document, Layer
from veccy.models.shapes import EllipseShape, LineTo, MoveTo, RectShape, Style
from veccy.render.overlay import CanvasColors, Overlay
from veccy.render.paths import PathCache
from veccy.render.scene import draw_background, draw_document, draw_overlays, parse_color

COLORS = CanvasColors("#101010", "#ffffff", "#808080", "#0000ff", "#00ff00")
TRANSPARENT = (0, 0, 0, 0)


def _render(doc: Document, moving=frozenset(), offset=(0.0, 0.0), background: bool = False) -> skia.Surface:
    surface = skia.Surface(int(doc.width), int(doc.height))
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    if background:
        draw_background(canvas, doc, COLORS)
    draw_document(canvas, doc, PathCache(), moving, offset)
    return surface


def _pixel(surface: skia.Surface, x: int, y: int) -> tuple[int, int, int, int]:
    rgba = surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
    return tuple(int(v) for v in rgba[y, x])


def _doc(*shapes, visible: bool = True) -> Document:
    return Document(100, 100, [Layer("L", visible, list(shapes))])


def test_parse_color_formats():
    assert parse_color("#ff0000") == 0xFFFF0000
    assert parse_color("#0f0") == 0xFF00FF00
    assert parse_color("#80000000") == 0x80000000


def test_filled_rect_colors_interior():
    surface = _render(_doc(RectShape(1, 10, 10, 50, 50, Style(fill="#ff0000", stroke=None))))
    assert _pixel(surface, 30, 30) == (255, 0, 0, 255)
    assert _pixel(surface, 80, 80) == TRANSPARENT


def test_no_fill_leaves_interior_and_stroke_colors_edge():
    shape = RectShape(1, 10, 10, 50, 50, Style(fill=None, stroke="#0000ff", stroke_width=4))
    surface = _render(_doc(shape))
    assert _pixel(surface, 30, 30) == TRANSPARENT
    assert _pixel(surface, 10, 30) == (0, 0, 255, 255)


def test_zero_stroke_width_draws_no_stroke():
    shape = RectShape(1, 10, 10, 50, 50, Style(fill=None, stroke="#0000ff", stroke_width=0))
    assert _pixel(_render(_doc(shape)), 10, 30) == TRANSPARENT


def test_hidden_layer_is_skipped():
    shape = RectShape(1, 10, 10, 50, 50, Style(fill="#ff0000", stroke=None))
    assert _pixel(_render(_doc(shape, visible=False)), 30, 30) == TRANSPARENT


def test_later_shape_paints_on_top():
    bottom = RectShape(1, 0, 0, 100, 100, Style(fill="#ff0000", stroke=None))
    top = EllipseShape(2, 50, 50, 20, 20, Style(fill="#00ff00", stroke=None))
    surface = _render(_doc(bottom, top))
    assert _pixel(surface, 50, 50) == (0, 255, 0, 255)
    assert _pixel(surface, 5, 5) == (255, 0, 0, 255)


def test_moving_shapes_draw_at_offset():
    shape = RectShape(1, 0, 0, 20, 20, Style(fill="#ff0000", stroke=None))
    surface = _render(_doc(shape), moving=frozenset({1}), offset=(60, 60))
    assert _pixel(surface, 10, 10) == TRANSPARENT
    assert _pixel(surface, 70, 70) == (255, 0, 0, 255)


def test_background_fills_artboard():
    surface = _render(_doc(), background=True)
    assert _pixel(surface, 50, 50) == (255, 255, 255, 255)


def _render_overlay(doc: Document, overlay, zoom: float = 1.0) -> skia.Surface:
    surface = skia.Surface(int(doc.width * zoom), int(doc.height * zoom))
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(zoom, zoom)
    draw_overlays(canvas, doc, overlay, PathCache(), zoom, COLORS)
    return surface


def test_selection_box_drawn_at_shape_bounds():
    doc = _doc(RectShape(1, 20, 20, 40, 40, Style(fill="#ff0000", stroke=None)))
    for zoom in (0.5, 1.0, 4.0):
        surface = _render_overlay(doc, Overlay(selection=frozenset({1})), zoom)
        edge = [_pixel(surface, int(20 * zoom), int(y * zoom)) for y in range(22, 58)]
        assert (0, 255, 0, 255) in edge
        assert _pixel(surface, int(40 * zoom), int(40 * zoom)) == TRANSPARENT


def test_selection_box_is_one_screen_px_wide():
    doc = _doc(RectShape(1, 20, 20, 40, 40, Style(fill="#ff0000", stroke=None)))
    surface = _render_overlay(doc, Overlay(selection=frozenset({1})), 4.0)
    counts = [sum(_pixel(surface, x, y) != TRANSPARENT for x in range(76, 86)) for y in range(100, 140)]
    assert max(counts) == 1


def test_rubber_band_fills_and_outlines():
    surface = _render_overlay(_doc(), Overlay(rubber_band=(10, 10, 50, 50)))
    inside = _pixel(surface, 30, 30)
    assert inside[1] > 0 and inside[3] < 255
    assert _pixel(surface, 80, 80) == TRANSPARENT


def test_preview_without_stroke_gets_hairline():
    segments = (MoveTo(10, 50), LineTo(90, 50))
    overlay = Overlay(preview=(segments, Style(fill=None, stroke=None)))
    assert _pixel(_render_overlay(_doc(), overlay), 50, 50) == (0, 0, 255, 255)


def test_preview_with_stroke_uses_tool_style():
    segments = (MoveTo(10, 50), LineTo(90, 50))
    overlay = Overlay(preview=(segments, Style(fill=None, stroke="#ff0000", stroke_width=4)))
    assert _pixel(_render_overlay(_doc(), overlay), 50, 50) == (255, 0, 0, 255)


def test_draw_document_ignores_overlay_state():
    shape = RectShape(1, 10, 10, 50, 50, Style(fill=None, stroke=None))
    assert _pixel(_render(_doc(shape)), 10, 30) == TRANSPARENT
