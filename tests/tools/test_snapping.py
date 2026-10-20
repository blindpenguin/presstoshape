import time
from dataclasses import replace

import pytest

from presstoshape.editing import queries
from presstoshape.editing.operations import guides, selection, shapes, view
from presstoshape.models.app_state import Tool
from presstoshape.models.layout import GridSettings
from presstoshape.models.shapes import RectShape, Style
from presstoshape.render.paths import PathCache
from presstoshape.tools.base import Mods
from tests.helpers import all_shapes, drag, setup_tools

NONE = Mods()
CTRL = Mods(ctrl=True)


def _box(shape):
    box = PathCache().geometry_bounds(shape)
    return box.left(), box.top(), box.right(), box.bottom()


def _select_setup():
    session, g = setup_tools()
    g.set_tool(Tool.SELECT)
    rect = shapes.add_rectangle(session, (200, 200), (220, 220))
    selection.set_selection(session, {rect})
    return session, g, rect


def test_moving_snaps_an_edge_to_a_guide_and_shows_it():
    session, g, rect = _select_setup()
    guides.add_guide(session, "vertical", 250)
    g.press((210, 210), NONE)
    g.move((236, 210), NONE)
    # (The rect's top also sits on the artboard's middle line, so that is a hit as well.)
    assert [hit.target for hit in g.overlay.snap if hit.axis == "x"] == ["guide"]
    g.release((236, 210), NONE)
    # The right edge (220 + 26 = 246) jumped to the guide at 250.
    assert _box(all_shapes(session)[0])[2] == pytest.approx(250)


def test_holding_ctrl_while_dragging_ignores_snapping():
    session, g, rect = _select_setup()
    guides.add_guide(session, "vertical", 250)
    g.press((210, 210), NONE)
    g.move((236, 210), CTRL)
    assert g.overlay.snap == ()
    g.release((236, 210), CTRL)
    assert _box(all_shapes(session)[0])[2] == pytest.approx(246)


def test_moving_lines_up_with_another_objects_centre_far_away():
    session, g, rect = _select_setup()
    shapes.add_rectangle(session, (500, 20), (540, 60))
    selection.set_selection(session, {rect})
    g.press((210, 210), NONE)
    # Moved by 308: the rect's centre (518) is 2 from the other object's centre (520).
    g.move((518, 210), NONE)
    hit = next(hit for hit in g.overlay.snap if hit.axis == "x")
    assert hit.target == "centre" and hit.line is not None
    g.release((518, 210), NONE)
    left, _top, right, _bottom = _box(all_shapes(session)[0])
    assert (left + right) / 2 == pytest.approx(520)


def test_grid_snaps_only_when_shown_and_checked():
    session, g, rect = _select_setup()
    session.state.document.grid = GridSettings(50, 2)
    view.set_snap_target(session, "objects", False)
    view.set_snap_target(session, "artboard", False)
    view.set_snap_target(session, "nodes", False)
    drag(g, (210, 210), (213, 214))
    assert _box(all_shapes(session)[0])[:2] == pytest.approx((203, 204))
    view.set_snap_target(session, "grid", True)
    view.toggle_grid(session)
    drag(g, (210, 210), (213, 214))
    # The left edge (203 + 3 = 206) is 6 from 200 and the top 7 from 200: both within 8 px.
    assert _box(all_shapes(session)[0])[:2] == pytest.approx((200, 200))


def test_snapping_switched_off_does_nothing():
    session, g, rect = _select_setup()
    guides.add_guide(session, "vertical", 250)
    view.toggle_snapping(session)
    drag(g, (210, 210), (236, 210))
    assert _box(all_shapes(session)[0])[2] == pytest.approx(246)


def test_scale_handle_snaps_to_a_guide():
    session, g, rect = _select_setup()
    guides.add_guide(session, "vertical", 300)
    drag(g, (220, 220), (296, 220))
    assert _box(all_shapes(session)[0])[2] == pytest.approx(300)


def test_drawing_a_rectangle_snaps_its_corners():
    session, g = setup_tools()
    guides.add_guide(session, "horizontal", 100)
    g.set_tool(Tool.RECTANGLE)
    drag(g, (10, 96), (60, 150))
    assert _box(all_shapes(session)[0])[1] == pytest.approx(100)


def test_node_drag_snaps_to_other_nodes_but_not_its_own_moving_ones():
    session, g = setup_tools()
    shapes.add_rectangle(session, (300, 300), (340, 340))
    path = shapes.add_path(session, [(100, 100), (200, 100), (200, 200)])
    view.select_tool(session, Tool.NODE)
    g.set_tool(Tool.NODE)
    selection.set_selection(session, {path})
    drag(g, (200, 200), (296, 296))
    edited = queries.find_shape(session.state, path)
    assert (edited.segments[-1].x, edited.segments[-1].y) == pytest.approx((300, 300))


def test_guides_drag_with_the_select_tool_and_snap_to_objects():
    session, g, rect = _select_setup()
    guide_id = guides.add_guide(session, "vertical", 400)
    selection.set_selection(session, set())
    assert g.hover((400, 50)).name == "GUIDE_VERTICAL"
    drag(g, (400, 50), (223, 50))
    assert session.state.document.guides[0].position == pytest.approx(220)
    assert session.undo_label == "Move guide"
    g.toolbox.context.pointer_off_canvas = True
    drag(g, (220, 50), (230, 50))
    assert session.state.document.guides == ()
    session.undo()
    assert session.state.document.guides[0].id == guide_id


def test_locked_or_hidden_guides_cant_be_dragged():
    session, g, rect = _select_setup()
    guides.add_guide(session, "vertical", 400)
    selection.set_selection(session, set())
    view.toggle_lock_guides(session)
    drag(g, (400, 50), (300, 50))
    assert session.state.document.guides[0].position == 400


def test_double_clicking_a_guide_asks_for_its_position():
    session, g, rect = _select_setup()
    guide_id = guides.add_guide(session, "horizontal", 300)
    asked = []
    g.toolbox.context.edit_guide = asked.append
    g.double_click((50, 301), NONE)
    assert asked == [guide_id]


def test_dragged_guide_preview_replaces_it():
    session, g, rect = _select_setup()
    guides.add_guide(session, "horizontal", 300)
    selection.set_selection(session, set())
    g.press((50, 300), NONE)
    g.move((50, 350), CTRL)
    preview = g.overlay.guide_preview
    assert preview is not None and preview.position == 350


def test_targets_build_quickly_for_a_large_drawing():
    session, g = setup_tools()
    layer = session.state.document.layers[0]
    style = Style()
    layer.shapes = [
        RectShape(index + 1, (index % 100) * 10, (index // 100) * 10, 8, 8, style) for index in range(10_000)
    ]
    session.state.document.next_id = 10_001
    g.toolbox.context.visible_rect = (0, 0, 400, 300)
    context = g.toolbox.context
    context.snapper()
    start = time.perf_counter()
    snapper = context.snapper(exclude={1})
    elapsed = time.perf_counter() - start
    assert snapper.point((401, 0)) != (401, 0)
    assert elapsed < 0.2
    session.state.snapping = replace(session.state.snapping, enabled=False)
    assert context.snapper().point((401, 0)) == (401, 0)
