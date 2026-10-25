import skia

from presstoshape.geometry import affine, transforms
from presstoshape.geometry.segments import rect_segments
from presstoshape.geometry.snapping import SnapHit
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.layout import GridSettings, Guide
from presstoshape.models.shapes import (
    CompositeShape,
    CubicTo,
    EllipseShape,
    GroupShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)
from presstoshape.render.export import render_png
from presstoshape.render.guides import draw_grid, draw_guides
from presstoshape.render.handles import Frame
from presstoshape.render.overlay import CanvasColors, NodeOverlay, Overlay
from presstoshape.render.paths import PathCache
from presstoshape.render.picture import EditModeDrawing
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


def test_subpath_start_nodes_are_drawn_larger():
    segments = (MoveTo(20, 20), LineTo(80, 20), MoveTo(20, 60), LineTo(80, 60))
    surface = _render_overlay(_doc(), Overlay(nodes=(NodeOverlay(segments),)), 1.0)
    for y in (20, 60):
        assert _pixel(surface, 20, y + 5) == (255, 255, 255, 255)
        assert _pixel(surface, 80, y + 5) != (255, 255, 255, 255)


def test_corner_nodes_are_diamonds_smooth_nodes_squares():
    smooth = (MoveTo(0, 50), CubicTo(10, 50, 30, 50, 50, 50), CubicTo(70, 50, 90, 50, 100, 50))
    corner = (MoveTo(0, 50), CubicTo(10, 50, 30, 50, 50, 50, corner=True), CubicTo(70, 50, 90, 50, 100, 50))
    for segments, inside in ((smooth, True), (corner, False)):
        surface = _render_overlay(_doc(), Overlay(nodes=(NodeOverlay(segments),)), 1.0)
        # A square's corner area; a diamond leaves it empty.
        assert (_pixel(surface, 52, 47) == (255, 255, 255, 255)) is inside


def test_corner_widgets_are_rings_in_the_warning_colour_when_limited():
    segments = (MoveTo(0, 0),)
    overlay = NodeOverlay(segments, widgets=((0, (30.0, 30.0)), (1, (70.0, 30.0))), limited=frozenset({1}))
    surface = _render_overlay(_doc(), Overlay(nodes=(overlay,)), 1.0)
    # Centre dot in the ring colour: selection (green) or warning (red, the default).
    r, g, b, _a = _pixel(surface, 30, 30)
    assert g > 200 and r < 80 and b < 80
    r, g, b, _a = _pixel(surface, 70, 30)
    assert r > 200 and g < 120 and b < 120


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


def _edit_surface(chain, overlay=Overlay(), drawing=None):
    doc = Document(100, 100, [Layer("L", True, [RectShape(99, 0, 0, 100, 100, Style(fill="#0000ff", stroke=None))])])
    surface = skia.Surface(100, 100)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    draw_document(canvas, doc, PathCache())
    if drawing is None:
        draw_edit_mode(canvas, chain, overlay, 1.0, COLORS)
    else:
        drawing.draw(canvas, chain, overlay, 1.0, COLORS)
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


RED = Style(fill="#ff0000", stroke=None)
BLUE = Style(fill="#0000ff", stroke=None)


def _overlapping_group(opacity: float = 1.0) -> GroupShape:
    return GroupShape(1, (RectShape(2, 10, 10, 40, 40, RED), RectShape(3, 30, 30, 40, 40, BLUE)), opacity)


def test_group_at_full_opacity_draws_like_its_shapes():
    loose = _render(_doc(*_overlapping_group().children)).makeImageSnapshot().toarray()
    grouped = _render(_doc(_overlapping_group())).makeImageSnapshot().toarray()
    assert (loose == grouped).all()


def test_group_opacity_flattens_the_shapes_first():
    surface = _render(_doc(_overlapping_group(0.5)))
    red, green, blue, alpha = _pixel(surface, 40, 40)
    # Where blue covers red, only blue shows, at half opacity: the red one doesn't shine through.
    assert red == 0 and blue > 0 and abs(alpha - 128) <= 1
    assert abs(_pixel(surface, 20, 20)[3] - 128) <= 1


def test_transparent_group_draws_nothing():
    assert _pixel(_render(_doc(_overlapping_group(0.0))), 40, 40) == TRANSPARENT


def test_entered_group_shows_its_shapes_undimmed_and_dragged_live():
    group = _overlapping_group()
    surface = _edit_surface([group])
    assert _pixel(surface, 20, 20) == (255, 0, 0, 255)
    assert _pixel(surface, 5, 5)[2] < 255
    moved = _edit_surface([group], Overlay(moving=frozenset({3}), matrix=affine.translation(20, 0)))
    assert _pixel(moved, 40, 40) == (255, 0, 0, 255)
    assert _pixel(moved, 80, 50) == (0, 0, 255, 255)


def test_recorded_edit_mode_drawing_matches_the_plain_one():
    outer = GroupShape(5, (_overlapping_group(), RectShape(6, 70, 70, 20, 20, RED)))
    chain = [outer, outer.children[0]]
    overlay = Overlay(moving=frozenset({3}), matrix=affine.translation(5, 5))
    plain = _edit_surface(chain, overlay).makeImageSnapshot().toarray()
    drawing = EditModeDrawing(PathCache())
    # Second frame replays the recorded pictures.
    for _frame in range(2):
        recorded = _edit_surface(chain, overlay, drawing).makeImageSnapshot().toarray()
        assert (recorded == plain).all()


def _surface_with(draw):
    surface = skia.Surface(100, 100)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    draw(canvas)
    return surface


def test_guides_are_one_pixel_lines_across_the_view():
    guides = (Guide(1, "vertical", 30.0), Guide(2, "horizontal", 60.0))
    surface = _surface_with(lambda canvas: draw_guides(canvas, guides, (0, 0, 100, 100), 0xFF00FFFF))
    assert _pixel(surface, 30, 5)[3] == 255 and _pixel(surface, 95, 60)[3] == 255
    assert _pixel(surface, 32, 5) == TRANSPARENT


def test_a_dragged_guide_is_drawn_at_its_preview_position():
    guides = (Guide(1, "vertical", 30.0),)
    preview = Guide(1, "vertical", 70.0)
    surface = _surface_with(lambda canvas: draw_guides(canvas, guides, (0, 0, 100, 100), 0xFF00FFFF, preview))
    assert _pixel(surface, 70, 5)[3] == 255 and _pixel(surface, 30, 5) == TRANSPARENT


def test_grid_draws_minor_and_major_lines_and_hides_dense_ones():
    grid = GridSettings(10.0, 5)
    surface = _surface_with(lambda canvas: draw_grid(canvas, grid, (0, 0, 100, 100), 1.0, 0xFF000000))
    minor, major = _pixel(surface, 10, 5)[3], _pixel(surface, 50, 5)[3]
    assert 0 < minor < major
    assert _pixel(surface, 15, 5) == TRANSPARENT

    def zoomed_out(canvas):
        canvas.scale(0.4, 0.4)
        draw_grid(canvas, grid, (0, 0, 250, 250), 0.4, 0xFF000000)

    surface = _surface_with(zoomed_out)
    # Minor lines would be 4 px apart: only the majors (every 20 px on screen) stay.
    assert _pixel(surface, 4, 5) == TRANSPARENT and _pixel(surface, 20, 5)[3] > 0


def test_snap_feedback_draws_a_line_and_a_label():
    hit = SnapHit("x", 50.0, "centre", ((50.0, 10.0), (50.0, 90.0)), (50.0, 10.0))
    overlay = Overlay(snap=(hit,))
    surface = _surface_with(lambda canvas: draw_overlays(canvas, [], overlay, PathCache(), 1.0, COLORS))
    assert any(_pixel(surface, 50, y)[3] > 0 for y in range(20, 80))
    assert any(_pixel(surface, x, 0)[3] > 0 for x in range(56, 80))


def test_png_export_has_no_guides_or_grid():
    doc = Document(100, 100, [Layer("L", True, [])], guides=(Guide(1, "vertical", 50.0),))
    assert render_png(doc, 1.0) == render_png(Document(100, 100, [Layer("L", True, [])]), 1.0)


def test_hidden_shape_is_not_drawn():
    red = Style(fill="#ff0000", stroke=None)
    surface = _render(_doc(RectShape(1, 10, 10, 50, 50, red, hidden=True)))
    assert _pixel(surface, 30, 30) == TRANSPARENT


def test_hidden_group_child_is_not_drawn():
    red, green = Style(fill="#ff0000", stroke=None), Style(fill="#00ff00", stroke=None)
    group = GroupShape(1, (RectShape(2, 0, 0, 40, 40, red), RectShape(3, 50, 50, 40, 40, green, hidden=True)))
    surface = _render(_doc(group))
    assert _pixel(surface, 20, 20) == (255, 0, 0, 255)
    assert _pixel(surface, 70, 70) == TRANSPARENT


def test_hidden_shape_is_not_exported():
    shape = RectShape(1, 0, 0, 100, 100, Style(fill="#ff0000", stroke=None), hidden=True)
    image = skia.Image.MakeFromEncoded(render_png(_doc(shape), 1.0))
    assert tuple(int(v) for v in image.toarray(colorType=skia.kRGBA_8888_ColorType)[50, 50]) == TRANSPARENT


def test_node_overlay_draws_extra_handles():
    segments = (MoveTo(20, 20),)
    overlay = Overlay(nodes=(NodeOverlay(segments, handles=(((20, 20), (60, 20)),)),))
    surface = _render_overlay(_doc(), overlay, 1.0)
    assert _pixel(surface, 40, 20)[3] > 0
    assert _pixel(surface, 60, 20) == (255, 255, 255, 255)
