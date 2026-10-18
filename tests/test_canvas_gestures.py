from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState, Tool
from veccy.models.shapes import PathShape, RectShape
from veccy.render.paths import PathCache
from veccy.views.canvas_gestures import CanvasGestures


def _setup(text: str | None = "hi") -> tuple[AppController, CanvasGestures]:
    c = AppController(AppState())
    g = CanvasGestures(c, PathCache(), repaint=lambda: None, ask_text=lambda: text)
    g.set_state(c.state)
    c.subscribe(lambda: g.set_state(c.state))
    return c, g


def _shapes(c: AppController):
    return [s for layer in c.state.document.layers for s in layer.shapes]


def _drag(g: CanvasGestures, a, b, shift=False, ctrl=False):
    g.press(a, shift, ctrl)
    g.move(b, shift)
    g.release(b, shift)


def test_rectangle_drag_adds_shape_with_shift_square():
    c, g = _setup()
    g.set_tool(Tool.RECTANGLE)
    _drag(g, (10, 10), (50, 30), shift=True)
    rect = _shapes(c)[0]
    assert isinstance(rect, RectShape) and rect.width == rect.height == 40


def test_preview_follows_drag_and_clears_on_release():
    c, g = _setup()
    g.set_tool(Tool.ELLIPSE)
    g.press((0, 0), False, False)
    g.move((40, 20), False)
    assert g.overlay.preview is not None
    g.release((40, 20), False)
    assert g.overlay.preview is None


def test_click_selects_and_empty_click_clears():
    c, g = _setup()
    sid = c.add_rectangle((0, 0), (50, 50))
    c.set_selection(set())
    _drag(g, (25, 25), (25, 25))
    assert c.state.selection == {sid}
    _drag(g, (200, 200), (200, 200))
    assert c.state.selection == set()


def test_ctrl_click_toggles():
    c, g = _setup()
    a = c.add_rectangle((0, 0), (50, 50))
    b = c.add_rectangle((100, 0), (150, 50))
    c.set_selection({a})
    _drag(g, (125, 25), (125, 25), ctrl=True)
    assert c.state.selection == {a, b}
    _drag(g, (25, 25), (25, 25), ctrl=True)
    assert c.state.selection == {b}


def test_drag_moves_selection_in_one_undo_step():
    c, g = _setup()
    sid = c.add_rectangle((0, 0), (50, 50))
    undo_depth = len(c._undo_stack)
    g.press((25, 25), False, False)
    g.move((35, 45), False)
    assert g.overlay.moving == {sid} and g.overlay.offset == (10, 20)
    assert _shapes(c)[0].x == 0
    g.release((35, 45), False)
    assert (_shapes(c)[0].x, _shapes(c)[0].y) == (10, 20)
    assert len(c._undo_stack) == undo_depth + 1


def test_rubber_band_selects_intersecting_and_ctrl_adds():
    c, g = _setup()
    a = c.add_rectangle((0, 0), (50, 50))
    b = c.add_rectangle((100, 100), (150, 150))
    c.set_selection(set())
    g.press((-10, -10), False, False)
    g.move((60, 60), False)
    assert g.overlay.rubber_band == (-10, -10, 70, 70)
    assert g.overlay.selection == {a}
    g.release((60, 60), False)
    assert c.state.selection == {a}
    _drag(g, (90, 90), (120, 120), ctrl=True)
    assert c.state.selection == {a, b}


def test_pen_finishes_with_deduped_points():
    c, g = _setup()
    g.set_tool(Tool.PEN)
    for p in [(0, 0), (50, 0), (50, 1), (100, 50)]:
        g.press(p, False, False)
    g.double_click()
    path = _shapes(c)[0]
    assert isinstance(path, PathShape)
    assert len(path.segments) == 3


def test_escape_cancels_gesture_then_clears_selection():
    c, g = _setup()
    sid = c.add_rectangle((0, 0), (50, 50))
    g.set_tool(Tool.PEN)
    g.press((0, 0), False, False)
    g.escape()
    assert g.overlay.preview is None
    assert c.state.selection == {sid}
    g.escape()
    assert c.state.selection == set()


def test_text_tool_uses_dialog_result():
    c, g = _setup(text="hello")
    g.set_tool(Tool.TEXT)
    g.press((10, 20), False, False)
    assert _shapes(c)[0].text == "hello"
    c2, g2 = _setup(text=None)
    g2.set_tool(Tool.TEXT)
    g2.press((10, 20), False, False)
    assert _shapes(c2) == []
