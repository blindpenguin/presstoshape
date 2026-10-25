from presstoshape.editing.operations import shapes
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import RectShape
from presstoshape.tools.base import CursorType, Mods
from tests.helpers import all_shapes, drag, setup_tools

NONE = Mods()


def test_rectangle_drag_adds_shape_with_shift_square():
    session, g = setup_tools()
    g.set_tool(Tool.RECTANGLE)
    drag(g, (10, 10), (50, 30), shift=True)
    rect = all_shapes(session)[0]
    assert isinstance(rect, RectShape) and rect.width == rect.height == 40


def test_preview_follows_drag_and_clears_on_release():
    session, g = setup_tools()
    g.set_tool(Tool.ELLIPSE)
    g.press((0, 0), NONE)
    g.move((40, 20), NONE)
    assert g.overlay.preview is not None
    g.release((40, 20), NONE)
    assert g.overlay.preview is None


def test_escape_cancels_gesture_then_clears_selection():
    session, g = setup_tools()
    sid = shapes.add_rectangle(session, (0, 0), (50, 50))
    g.set_tool(Tool.PEN)
    g.press((0, 0), NONE)
    g.escape()
    assert g.overlay.preview is None
    assert session.state.selection == {sid}
    g.escape()
    assert session.state.selection == set()


def test_text_tool_uses_dialog_result():
    session, g = setup_tools(text="hello")
    g.set_tool(Tool.TEXT)
    g.press((10, 20), NONE)
    assert all_shapes(session)[0].text == "hello"
    session2, g2 = setup_tools(text=None)
    g2.set_tool(Tool.TEXT)
    g2.press((10, 20), NONE)
    assert all_shapes(session2) == []


def test_hover_drawing_tools():
    session, g = setup_tools()
    g.set_tool(Tool.RECTANGLE)
    assert g.hover((0, 0)) is CursorType.CROSS
    g.set_tool(Tool.TEXT)
    assert g.hover((0, 0)) is CursorType.IBEAM
