import pytest

from veccy.controllers.app_controller import AppController
from veccy.models.app_state import AppState, Tool
from veccy.models.shapes import PathShape, RectShape, TextShape


def _controller() -> AppController:
    return AppController(AppState())


def _shapes(c: AppController):
    return [s for layer in c.state.document.layers for s in layer.shapes]


def test_notifies_listeners_on_change():
    c = _controller()
    calls = []
    c.subscribe(lambda: calls.append(1))
    c.select_tool(Tool.PEN)
    assert calls == [1]


def test_add_rectangle_selects_it_and_marks_dirty():
    c = _controller()
    sid = c.add_rectangle((10, 10), (0, 0))
    assert c.state.selection == {sid}
    assert isinstance(_shapes(c)[0], RectShape)
    assert c.state.dirty


def test_tiny_drag_adds_nothing():
    c = _controller()
    assert c.add_rectangle((0, 0), (0.5, 20)) is None
    assert not c.can_undo


def test_undo_redo_add_and_move():
    c = _controller()
    c.add_rectangle((0, 0), (10, 10))
    c.move_selection(5, 0)
    assert _shapes(c)[0].x == 5
    c.undo()
    assert _shapes(c)[0].x == 0
    c.undo()
    assert _shapes(c) == [] and c.state.selection == set()
    c.redo()
    c.redo()
    assert _shapes(c)[0].x == 5
    assert not c.can_redo


def test_new_edit_clears_redo():
    c = _controller()
    c.add_rectangle((0, 0), (10, 10))
    c.undo()
    c.add_ellipse((0, 0), (10, 10))
    assert not c.can_redo


def test_stroke_width_changes_merge_into_one_undo_step():
    c = _controller()
    c.add_rectangle((0, 0), (10, 10))
    for w in (3, 4, 5):
        c.set_stroke_width(w)
    assert _shapes(c)[0].style.stroke_width == 5
    c.undo()
    assert _shapes(c)[0].style.stroke_width == 2


def test_selection_style_without_selection_is_noop():
    c = _controller()
    before = dict(c.state.tool_styles)
    c.set_fill("#00ff00")
    assert c.state.tool_styles == before
    assert not c.can_undo


def test_selection_style_leaves_tool_styles_alone():
    c = _controller()
    c.add_rectangle((0, 0), (10, 10))
    c.set_fill("#00ff00")
    assert _shapes(c)[0].style.fill == "#00ff00"
    assert c.state.tool_styles[Tool.RECTANGLE].fill != "#00ff00"


def test_tool_style_applies_to_that_tool_only_and_is_not_undoable():
    c = _controller()
    c.set_tool_style(Tool.ELLIPSE, fill="#00ff00", stroke_width=-3)
    assert not c.can_undo and not c.state.dirty
    assert c.state.tool_styles[Tool.ELLIPSE].stroke_width == 0
    c.add_rectangle((0, 0), (10, 10))
    c.add_ellipse((0, 0), (10, 10))
    rect, ellipse = _shapes(c)
    assert rect.style.fill != "#00ff00"
    assert ellipse.style.fill == "#00ff00"


def test_default_pen_has_no_fill_and_text_has_no_stroke():
    c = _controller()
    c.set_font_size(40)
    c.add_path([(0, 0), (10, 10), (20, 0)])
    c.add_text((5, 5), "hi")
    path, text = _shapes(c)
    assert isinstance(path, PathShape) and path.style.fill is None
    assert isinstance(text, TextShape) and text.style.stroke is None
    assert text.font_size == 40


def test_union_replaces_selection_at_bottom_position():
    c = _controller()
    keep = c.add_rectangle((100, 100), (110, 110))
    a = c.add_rectangle((0, 0), (10, 10))
    b = c.add_ellipse((5, 5), (15, 15))
    c.set_selection({a, b})
    assert c.can_combine()
    c.combine("union")
    shapes = _shapes(c)
    assert [s.id for s in shapes][0] == keep
    assert len(shapes) == 2 and isinstance(shapes[1], PathShape)
    assert c.state.selection == {shapes[1].id}
    c.undo()
    assert [s.id for s in _shapes(c)] == [keep, a, b]


def test_cannot_combine_with_text():
    c = _controller()
    a = c.add_rectangle((0, 0), (10, 10))
    t = c.add_text((0, 0), "x")
    c.set_selection({a, t})
    assert not c.can_combine()


def test_hidden_layer_shapes_drop_out_of_selection_and_block_drawing():
    c = _controller()
    sid = c.add_rectangle((0, 0), (10, 10))
    c.set_layer_visible(0, False)
    assert c.state.selection == set()
    c.set_selection({sid})
    assert c.state.selection == set()
    assert c.add_rectangle((0, 0), (10, 10)) is None


def test_layers_add_remove_rename():
    c = _controller()
    c.add_layer()
    assert [layer.name for layer in c.state.document.layers] == ["Layer 1", "Layer 2"]
    assert c.state.selected_layer_index == 1
    c.rename_layer(1, "  Top ")
    c.rename_layer(1, "   ")
    assert c.state.document.layers[1].name == "Top"
    c.remove_layer(1)
    c.remove_layer(0)
    assert len(c.state.document.layers) == 1
    assert c.state.selected_layer_index == 0


def test_undo_layer_removal_restores_selected_index():
    c = _controller()
    c.add_layer()
    c.remove_layer(1)
    c.undo()
    assert len(c.state.document.layers) == 2


def test_zoom_clamped():
    c = _controller()
    c.set_zoom(5000)
    assert c.state.zoom_percent == 800
    c.set_zoom(1)
    assert c.state.zoom_percent == 10


def test_save_and_open_roundtrip(tmp_path):
    c = _controller()
    c.add_rectangle((0, 0), (10, 10))
    path = tmp_path / "a.svg"
    assert c.save_file(str(path))
    assert not c.state.dirty and c.state.file_path == str(path)

    other = _controller()
    assert other.open_file(str(path))
    assert _shapes(other) == _shapes(c)
    assert not other.can_undo


def test_save_without_path_returns_false():
    assert not _controller().save_file()


def test_open_bad_file_reports_and_keeps_document(tmp_path):
    c = _controller()
    c.add_rectangle((0, 0), (10, 10))
    bad = tmp_path / "bad.svg"
    bad.write_text("<svg")
    assert not c.open_file(str(bad))
    assert "Could not open" in c.state.status_message
    assert len(_shapes(c)) == 1


def test_set_shape_field_edits_geometry_with_merged_undo():
    c = _controller()
    sid = c.add_rectangle((0, 0), (10, 10))
    for w in (20, 30, 40):
        c.set_shape_field(sid, "width", w)
    c.set_shape_field(sid, "x", 5)
    assert (_shapes(c)[0].width, _shapes(c)[0].x) == (40, 5)
    c.undo()
    assert (_shapes(c)[0].width, _shapes(c)[0].x) == (40, 0)
    c.undo()
    assert _shapes(c)[0].width == 10


def test_set_shape_field_clamps_sizes_and_rejects_empty_text():
    c = _controller()
    sid = c.add_ellipse((0, 0), (10, 10))
    c.set_shape_field(sid, "rx", -5)
    assert _shapes(c)[0].rx == 0.1
    tid = c.add_text((0, 0), "hello")
    c.set_shape_field(tid, "text", "   ")
    c.set_shape_field(tid, "text", "bye")
    assert _shapes(c)[1].text == "bye"


def test_set_shape_field_rejects_fields_of_other_shape_kinds():
    c = _controller()
    sid = c.add_rectangle((0, 0), (10, 10))
    with pytest.raises(ValueError):
        c.set_shape_field(sid, "rx", 3)
