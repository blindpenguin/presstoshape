import pytest

from veccy.render.viewport import SCENE_MARGIN, Viewport, scene_rect


def _vp(zoom: float = 1.0, scroll: tuple[float, float] = (0.0, 0.0)) -> Viewport:
    return Viewport(zoom, *scroll, width=800, height=600, scene=scene_rect(600, 400)).clamped()


def test_scene_rect_adds_margin():
    assert scene_rect(600, 400) == (-SCENE_MARGIN, -SCENE_MARGIN, 600 + 2 * SCENE_MARGIN, 400 + 2 * SCENE_MARGIN)


def test_to_doc_inverts_to_screen():
    vp = _vp(2.5, (-300, -200))
    x, y = vp.to_doc(vp.to_screen((123.0, -45.0)))
    assert x == pytest.approx(123.0)
    assert y == pytest.approx(-45.0)


def test_scroll_value_is_screen_offset_of_scene():
    vp = _vp(1.0, (-100, -50))
    assert vp.to_screen((0, 0)) == (100, 50)


def test_scroll_is_clamped_to_scene():
    vp = _vp(1.0, (-1e9, 1e9))
    min_x, _, _, max_y = vp.scroll_range()
    assert (vp.scroll_x, vp.scroll_y) == (min_x, max_y)


def test_small_scene_is_centered():
    vp = Viewport(1.0, 0, 0, width=800, height=600, scene=(0, 0, 200, 100))
    assert vp.to_screen((100, 50)) == (400, 300)


def test_matrix_matches_to_screen_with_dpr():
    vp = _vp(1.5, (-200, -100))
    m = vp.matrix(2.0)
    sx, sy = vp.to_screen((10, 20))
    p = m.mapXY(10, 20)
    assert (p.x(), p.y()) == (pytest.approx(sx * 2), pytest.approx(sy * 2))


def test_zoom_at_keeps_anchor_fixed():
    vp = _vp(1.0, (-200, -100))
    anchor = (300.0, 250.0)
    doc_point = vp.to_doc(anchor)
    zoomed, residual = vp.zoom_at(3.0, anchor)
    sx, sy = zoomed.to_screen(doc_point)
    assert abs(sx - anchor[0]) <= 0.5 and abs(sy - anchor[1]) <= 0.5
    assert zoomed.zoom == 3.0
    assert all(abs(r) <= 0.5 for r in residual)


def test_repeated_zoom_steps_do_not_creep():
    vp = _vp(1.0, (-200, -100))
    anchor = (333.0, 211.0)
    doc_point = vp.to_doc(anchor)
    residual = (0.0, 0.0)
    for _ in range(20):
        vp, residual = vp.zoom_at(vp.zoom * 1.15, anchor, residual)
    for _ in range(20):
        vp, residual = vp.zoom_at(vp.zoom / 1.15, anchor, residual)
    sx, sy = vp.to_screen(doc_point)
    assert abs(sx - anchor[0]) <= 1 and abs(sy - anchor[1]) <= 1


def test_scrolled_moves_by_delta():
    vp = _vp(1.0, (-200, -100))
    moved = vp.scrolled(30, -20)
    assert (moved.scroll_x, moved.scroll_y) == (-170, -120)
