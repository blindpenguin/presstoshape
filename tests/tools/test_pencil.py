import math

from presstoshape.editing import containers
from presstoshape.editing.operations import composites, layers, selection, shapes, view
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import Close, CubicTo, LineTo, PathShape
from presstoshape.tools.base import Mods
from tests.helpers import all_shapes, setup_tools

NONE = Mods()


def _wave(count=200, amplitude=30.0, noise=0.0):
    return [(100 + i * 2, 200 + amplitude * math.sin(i / 12) + noise * ((i * 7919) % 5 - 2)) for i in range(count)]


def _stroke(driver, points, finish=True):
    driver.set_tool(Tool.PENCIL)
    driver.press(points[0], NONE)
    for point in points[1:]:
        driver.move(point, NONE)
    if finish:
        driver.release(points[-1], NONE)


def test_drag_draws_a_smooth_selected_path_in_one_undo_step():
    session, driver = setup_tools()
    undo_depth = session.undo_count
    _stroke(driver, _wave())
    (path,) = all_shapes(session)
    assert isinstance(path, PathShape)
    cubics = [segment for segment in path.segments if isinstance(segment, CubicTo)]
    assert 1 < len(cubics) < 30
    assert path.style == session.state.tool_styles[Tool.PENCIL]
    assert session.state.selection == {path.id}
    assert session.undo_count == undo_depth + 1 and session.undo_label == "Add path"


def test_preview_is_the_raw_stroke_in_the_pencil_style():
    session, driver = setup_tools()
    _stroke(driver, _wave(40), finish=False)
    segments, style = driver.overlay.preview
    assert style == session.state.tool_styles[Tool.PENCIL]
    assert len(segments) == 40 and all(isinstance(segment, LineTo) for segment in segments[1:])
    assert all_shapes(session) == []


def test_escape_cancels_and_a_click_creates_nothing():
    session, driver = setup_tools()
    _stroke(driver, _wave(40), finish=False)
    driver.escape()
    assert driver.overlay.preview is None and all_shapes(session) == []
    _stroke(driver, [(50, 50), (50.5, 50.2), (51, 50)])
    assert all_shapes(session) == []


def test_ending_near_the_start_closes_the_path():
    session, driver = setup_tools()
    loop = [(300 + 100 * math.cos(a / 30), 300 + 100 * math.sin(a / 30)) for a in range(0, 189)]
    _stroke(driver, loop)
    (path,) = all_shapes(session)
    assert isinstance(path.segments[-1], Close)


def test_inside_a_composite_the_stroke_becomes_a_part():
    session, driver = setup_tools()
    bottom = shapes.add_rectangle(session, (0, 0), (400, 400))
    top = shapes.add_rectangle(session, (50, 50), (150, 150))
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session)
    (composite,) = session.state.selection
    composites.enter(session, composite)
    composites.set_new_part_mode(session, "subtract")
    _stroke(driver, _wave(60))
    edited = containers.edited_composite(session.state)
    assert len(edited.parts) == 3 and edited.modes[-1] == "subtract"


def test_hidden_layer_refuses_with_a_message():
    session, driver = setup_tools()
    layers.set_layer_visible(session, 0, False)
    _stroke(driver, _wave(60))
    assert all_shapes(session) == [] and "hidden" in session.state.status_message


def test_more_smoothing_gives_fewer_nodes():
    counts = []
    for smoothing in (0, 100):
        session, driver = setup_tools()
        view.set_pencil_smoothing(session, smoothing)
        _stroke(driver, _wave(300, noise=1.5))
        (path,) = all_shapes(session)
        counts.append(len(path.segments))
    assert counts[1] < counts[0]
