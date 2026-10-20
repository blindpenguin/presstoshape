import skia

from presstoshape.geometry import affine, transforms
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import (
    CompositeShape,
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)
from presstoshape.render.export import render_png
from presstoshape.render.handles import Frame
from presstoshape.render.overlay import CanvasColors, NodeOverlay, Overlay
from presstoshape.render.paths import PathCache
from presstoshape.render.scene import (
    draw_background,
    draw_document,
    draw_edit_mode,
    draw_overlays,
    parse_color,
    visible_shapes,
)

COLORS = CanvasColors("#101010", "#ffffff", "#808080", "#0000ff", "#00ff00")
TRANSPARENT = (0, 0, 0, 0)


def _render(
    doc: Document, moving=frozenset(), matrix=affine.IDENTITY, background: bool = False, live=()
) -> skia.Surface:
    surface = skia.Surface(int(doc.width), int(doc.height))
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    if background:
        draw_background(canvas, doc, COLORS)
    draw_document(canvas, doc, PathCache(), moving, matrix, live)
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
    surface = _render(_doc(shape), moving=frozenset({1}), matrix=affine.translation(60, 60))
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
    draw_overlays(canvas, list(visible_shapes(doc)), overlay, PathCache(), zoom, COLORS)
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


def test_rotated_rect_renders_rotated():
    # 60x20 bar rotated 90° about its center (50, 50) becomes a 20x60 bar.
    rect = transforms.with_rotation(RectShape(1, 20, 40, 60, 20, Style(fill="#ff0000", stroke=None)), 90)
    surface = _render(_doc(rect))
    assert _pixel(surface, 50, 25) == (255, 0, 0, 255)
    assert _pixel(surface, 25, 50) == TRANSPARENT


def test_live_shapes_replace_moving_shapes():
    shape = RectShape(1, 0, 0, 20, 20, Style(fill="#ff0000", stroke=None))
    live = (RectShape(1, 50, 50, 40, 40, Style(fill="#ff0000", stroke=None)),)
    surface = _render(_doc(shape), moving=frozenset({1}), live=live)
    assert _pixel(surface, 10, 10) == TRANSPARENT
    assert _pixel(surface, 85, 85) == (255, 0, 0, 255)


def test_frame_handles_are_eight_screen_px():
    doc = _doc(RectShape(1, 20, 20, 20, 20, Style(fill=None, stroke=None)))
    frame = Frame((20, 20, 20, 20))
    surface = _render_overlay(doc, Overlay(selection=frozenset({1}), frame=frame), 2.0)
    # SE handle centered at (40, 40) doc = (80, 80) px; 8 px wide white square with a 1 px border.
    row = [_pixel(surface, x, 82) != TRANSPARENT for x in range(70, 91)]
    assert sum(row) == 9
    assert _pixel(surface, 82, 82) == (255, 255, 255, 255)


def test_single_selection_with_frame_has_no_dashed_box():
    doc = _doc(RectShape(1, 20, 20, 40, 40, Style(fill=None, stroke=None)))
    frame = Frame((20, 20, 40, 40))
    surface = _render_overlay(doc, Overlay(selection=frozenset({1}), frame=frame), 1.0)
    edge = {_pixel(surface, 20, y) for y in range(26, 34)}
    assert edge == {(0, 255, 0, 255)}


def test_selected_node_is_filled_unselected_is_white():
    segments = (MoveTo(20, 20), LineTo(80, 20))
    overlay = Overlay(nodes=(NodeOverlay(segments, selected=frozenset({1})),))
    surface = _render_overlay(_doc(), overlay, 1.0)
    assert _pixel(surface, 20, 20) == (255, 255, 255, 255)
    assert _pixel(surface, 80, 20) == (0, 255, 0, 255)


def _ring(shape_id=10, style=Style(fill="#ff0000", stroke=None)):
    outer = RectShape(1, 20, 20, 60, 60, style)
    hole = RectShape(2, 40, 40, 20, 20, style)
    return CompositeShape(shape_id, (outer, hole), ("add", "subtract"), style)


def test_composite_renders_its_result_not_its_parts():
    surface = _render(_doc(_ring()))
    assert _pixel(surface, 25, 25) == (255, 0, 0, 255)
    assert _pixel(surface, 50, 50) == TRANSPARENT


def test_composite_export_matches_canvas():
    data = render_png(_doc(_ring()), 1.0)
    image = skia.Image.MakeFromEncoded(skia.Data.MakeWithCopy(data))
    rgba = image.toarray(colorType=skia.kRGBA_8888_ColorType)
    assert tuple(int(v) for v in rgba[25, 25]) == (255, 0, 0, 255)
    assert tuple(int(v) for v in rgba[50, 50]) == TRANSPARENT


def _edit_surface(chain, overlay=Overlay()):
    doc = Document(100, 100, [Layer("L", True, [RectShape(99, 0, 0, 100, 100, Style(fill="#0000ff", stroke=None))])])
    surface = skia.Surface(100, 100)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    draw_document(canvas, doc, PathCache())
    draw_edit_mode(canvas, chain, overlay, 1.0, COLORS)
    return surface


def test_edit_mode_dims_outside_and_draws_the_live_result():
    ring = _ring()
    surface = _edit_surface([ring])
    # Outside the Composite: the blue background is dimmed toward the pasteboard color.
    dimmed = _pixel(surface, 5, 5)
    assert dimmed != (0, 0, 255, 255) and dimmed[2] < 255
    # The Composite's result is drawn undimmed on top.
    assert _pixel(surface, 25, 25) == (255, 0, 0, 255)


def test_edit_mode_shows_a_dragged_part_live():
    ring = _ring()
    overlay = Overlay(moving=frozenset({2}), matrix=affine.translation(-20, -20))
    surface = _edit_surface([ring], overlay)
    # The hole moved up-left to 20..40, so (30, 30) is now a hole and (50, 50) is filled.
    assert _pixel(surface, 50, 50) == (255, 0, 0, 255)
    assert _pixel(surface, 30, 30) != (255, 0, 0, 255)


def _square_ring(fill_rule: str) -> PathShape:
    # Both squares wound the same way, so only evenodd leaves the inner one open.
    segments = rect_segments(10, 10, 60, 60) + rect_segments(30, 30, 20, 20)
    return PathShape(1, segments, Style(fill="#ff0000", stroke=None, fill_rule=fill_rule))


def test_evenodd_leaves_the_hole_open():
    assert _pixel(_render(_doc(_square_ring("evenodd"))), 40, 40) == TRANSPARENT
    assert _pixel(_render(_doc(_square_ring("nonzero"))), 40, 40) == (255, 0, 0, 255)
    assert _pixel(_render(_doc(_square_ring("evenodd"))), 20, 20) == (255, 0, 0, 255)


def test_object_opacity_flattens_fill_and_stroke():
    style = Style(fill="#ff0000", stroke="#0000ff", stroke_width=10, opacity=0.5)
    red, green, blue, alpha = _pixel(_render(_doc(RectShape(1, 20, 20, 50, 50, style))), 22, 40)
    # Inside half of the stroke: only the stroke shows, the fill underneath doesn't shine through.
    assert red == 0 and blue > 0 and abs(alpha - 128) <= 1


def test_object_opacity_with_one_paint():
    style = Style(fill="#ff0000", stroke=None, opacity=0.5)
    assert abs(_pixel(_render(_doc(RectShape(1, 20, 20, 50, 50, style))), 40, 40)[3] - 128) <= 1


def test_fill_and_stroke_opacity_apply_to_their_paint():
    style = Style(fill="#ff0000", stroke="#0000ff", stroke_width=10, fill_opacity=0.25, stroke_opacity=0.5)
    surface = _render(_doc(RectShape(1, 20, 20, 50, 50, style)))
    assert abs(_pixel(surface, 45, 45)[3] - 64) <= 1
    assert abs(_pixel(surface, 16, 45)[3] - 128) <= 1


def test_zero_opacity_draws_nothing():
    style = Style(fill="#ff0000", stroke="#0000ff", opacity=0)
    assert _pixel(_render(_doc(RectShape(1, 20, 20, 50, 50, style))), 40, 40) == TRANSPARENT


def _line(**style_fields) -> PathShape:
    style = Style(fill=None, stroke="#000000", stroke_width=10, **style_fields)
    return PathShape(1, (MoveTo(20, 50), LineTo(80, 50)), style)


def test_dashes_leave_gaps():
    surface = _render(_doc(_line(dashes=(10.0, 10.0))))
    assert _pixel(surface, 25, 50)[3] == 255
    assert _pixel(surface, 35, 50) == TRANSPARENT


def test_round_cap_reaches_past_the_end_point():
    assert _pixel(_render(_doc(_line(cap="round"))), 83, 50)[3] == 255
    assert _pixel(_render(_doc(_line())), 83, 50) == TRANSPARENT


def test_rounded_rect_corners_are_open():
    shape = RectShape(1, 10, 10, 60, 60, Style(fill="#ff0000", stroke=None), rx=15, ry=15)
    surface = _render(_doc(shape))
    assert _pixel(surface, 11, 11) == TRANSPARENT
    assert _pixel(surface, 40, 40) == (255, 0, 0, 255)


def test_text_anchor_moves_the_line():
    cache = PathCache()
    start = cache.geometry_bounds(TextShape(1, 50, 50, "Wide", 20, Style()))
    middle = cache.geometry_bounds(TextShape(2, 50, 50, "Wide", 20, Style(), anchor="middle"))
    end = cache.geometry_bounds(TextShape(3, 50, 50, "Wide", 20, Style(), anchor="end"))
    assert start.fLeft >= 49
    assert abs((middle.fLeft + middle.fRight) / 2 - 50) < 2
    assert end.fRight <= 51


def test_anchored_text_draws_where_its_outline_is():
    shape = TextShape(1, 50, 60, "I", 40, Style(fill="#000000", stroke=None), anchor="end")
    bounds = PathCache().geometry_bounds(shape)
    surface = _render(_doc(shape))
    assert _pixel(surface, round((bounds.fLeft + bounds.fRight) / 2), round(bounds.centerY()))[3] == 255
