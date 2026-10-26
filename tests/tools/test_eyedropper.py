from presstoshape.editing.operations import selection
from presstoshape.models.app_state import Document, Layer, Tool
from presstoshape.models.shapes import GroupShape, ImageShape, RectShape, Style
from presstoshape.tools.base import Mods
from tests.helpers import setup_tools, tiny_image

SOURCE = Style(fill="#ff0000", stroke="#00ff00", stroke_width=6.0, dashes=(3.0, 1.0))


def setup(sampled="#123456"):
    session, driver = setup_tools()
    target = RectShape(1, 0, 0, 10, 10, Style())
    source = GroupShape(3, (RectShape(2, 20, 0, 10, 10, SOURCE, locked=True),))
    picture = ImageShape(4, 40, 0, 10, 10, tiny_image())
    session.state.document = Document(layers=[Layer("L", True, [target, source, picture])], next_id=5)
    driver.toolbox.context.sample_color = lambda point: sampled
    driver.set_tool(Tool.EYEDROPPER)
    return session, driver


def shapes(session):
    return session.state.document.layers[0].shapes


def test_click_gives_the_selection_the_whole_style():
    session, driver = setup()
    selection.set_selection(session, {1})
    driver.press((25, 5), Mods())
    assert shapes(session)[0].style == SOURCE
    assert session.state.selection == {1}
    assert session.undo_label == "Pick up style"


def test_click_without_selection_fills_current_colour():
    session, driver = setup()
    driver.press((25, 5), Mods())
    current = session.state.colours.current
    assert (current.fill, current.stroke) == ("#ff0000", "#00ff00")
    assert not session.can_undo


def test_shift_click_samples_into_the_active_paint():
    session, driver = setup()
    selection.set_selection(session, {1})
    session.state.colours.active = "stroke"
    driver.press((25, 5), Mods(shift=True))
    assert shapes(session)[0].style.stroke == "#123456"
    assert shapes(session)[0].style.fill == Style().fill


def test_click_on_a_picture_samples_it():
    session, driver = setup("#abcdef")
    selection.set_selection(session, {1})
    driver.press((45, 5), Mods())
    assert shapes(session)[0].style.fill == "#abcdef"


def test_empty_canvas_does_nothing():
    session, driver = setup(None)
    selection.set_selection(session, {1})
    driver.press((200, 200), Mods())
    driver.press((200, 200), Mods(shift=True))
    assert shapes(session)[0].style == Style()
    assert not session.can_undo


def test_cursor():
    _session, driver = setup()
    assert driver.hover((5, 5)).name == "EYEDROPPER"
