import pytest
from PySide6.QtWidgets import QApplication, QWidget

from presstoshape.editing.operations import selection, shapes, view
from presstoshape.editing.session import Session
from presstoshape.geometry import units
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import Style
from presstoshape.views.actions import AppActions
from presstoshape.views.selection_view import SelectionOptions
from presstoshape.views.style_editor import ALL_FIELDS, StyleEditor
from presstoshape.views.tool_options_view import ToolOptionsPanel
from tests.helpers import all_shapes


@pytest.fixture
def editor():
    QApplication.instance() or QApplication([])
    changes = []
    widget = StyleEditor(ALL_FIELDS, changes.append)
    return widget, changes


def _visible(editor, widget) -> bool:
    return editor.form.isRowVisible(widget)


def test_refresh_never_reports_changes(editor):
    widget, changes = editor
    full = Style(opacity=0.3, fill_opacity=0.4, cap="round", join="bevel", dashes=(4, 2), dash_offset=1)
    for style in (Style(), Style(fill=None, stroke=None), full):
        widget.refresh(style)
    assert changes == []
    assert widget._opacity.slider.value() == 30 and widget._fill.opacity.value() == 40


def test_stroke_options_follow_the_stroke(editor):
    widget, _changes = editor
    widget.refresh(Style(stroke=None))
    assert not _visible(widget, widget._cap) and not _visible(widget, widget._dash_edit)
    widget.refresh(Style(join="miter"))
    assert _visible(widget, widget._cap) and _visible(widget, widget._miter)
    assert not _visible(widget, widget._dash_offset)
    widget.refresh(Style(join="round", dashes=(1, 1)))
    assert not _visible(widget, widget._miter) and _visible(widget, widget._dash_offset)


def test_fill_rule_follows_the_fill(editor):
    widget, _changes = editor
    widget.refresh(Style(fill=None))
    assert not _visible(widget, widget._fill_rule)
    widget.refresh(Style(fill="#ff0000"))
    assert _visible(widget, widget._fill_rule)


def test_edits_report_one_field_each(editor):
    widget, changes = editor
    widget.refresh(Style())
    widget._cap.activated.emit(1)
    widget._join.activated.emit(2)
    widget._fill_rule.activated.emit(1)
    widget._opacity.box.setValue(50)
    widget._stroke.opacity.setValue(25)
    assert changes == [
        {"cap": "round"},
        {"join": "bevel"},
        {"fill_rule": "evenodd"},
        {"opacity": 0.5},
        {"stroke_opacity": 0.25},
    ]


def test_dashes_are_entered_in_the_document_unit(editor):
    widget, changes = editor
    widget.set_unit("mm", 96)
    widget.refresh(Style(dashes=(units.to_px(2, "mm", 96), units.to_px(1, "mm", 96))))
    assert widget._dash_edit.text() == "2 1"
    widget._dash_edit.setText("4, 2")
    widget._dash_edit.editingFinished.emit()
    assert changes == [{"dashes": pytest.approx((units.to_px(4, "mm", 96), units.to_px(2, "mm", 96)))}]


def test_bad_dash_text_shows_the_shape_again(editor):
    widget, changes = editor
    widget.refresh(Style(dashes=(3, 1)))
    widget._dash_edit.setText("lots")
    widget._dash_edit.editingFinished.emit()
    assert changes == [] and widget._dash_edit.text() == "3 1"


def _panel():
    QApplication.instance() or QApplication([])
    session = Session()
    panel = SelectionOptions(session)
    session.subscribe(lambda: panel.refresh(session.state))
    return session, panel


def test_selection_panel_edits_the_selection():
    session, panel = _panel()
    rect = shapes.add_rectangle(session, (0, 0), (10, 10))
    selection.set_selection(session, {rect})
    panel._style._join.activated.emit(1)
    assert all_shapes(session)[0].style.join == "round"
    assert session.undo_label == "Change line join"


def test_corner_radius_row_for_rectangles_with_mixed_values():
    session, panel = _panel()
    first = shapes.add_rectangle(session, (0, 0), (10, 10))
    second = shapes.add_rectangle(session, (20, 0), (30, 10))
    ellipse = shapes.add_ellipse(session, (40, 0), (50, 10))
    selection.set_selection(session, {first, second})
    assert panel._form.isRowVisible(panel._radius)
    panel._radius.setValue(2)
    assert [shape.rx for shape in all_shapes(session)[:2]] == [2, 2]
    selection.set_selection(session, {first})
    shapes.set_corner_radius(session, 4)
    selection.set_selection(session, {first, second})
    assert panel._radius.text() == "Mixed"
    selection.set_selection(session, {first, ellipse})
    assert not panel._form.isRowVisible(panel._radius)


def test_alignment_buttons_for_text():
    session, panel = _panel()
    text = shapes.add_text(session, (10, 10), "Hi")
    selection.set_selection(session, {text})
    assert panel._form.isRowVisible(panel._anchor_row)
    assert panel._anchor_buttons["start"].isChecked()
    panel._anchor_buttons["end"].click()
    assert all_shapes(session)[0].anchor == "end"
    assert panel._anchor_buttons["end"].isChecked() and not panel._anchor_buttons["start"].isChecked()
    panel._anchor_buttons["end"].click()
    assert panel._anchor_buttons["end"].isChecked()


def test_tool_options_change_the_tool_style():
    QApplication.instance() or QApplication([])
    session = Session()
    actions = AppActions(QWidget(), session, {})
    panel = ToolOptionsPanel(session, actions)
    session.subscribe(lambda: panel.refresh(session.state))
    view.select_tool(session, Tool.PEN)
    panel._editors[Tool.PEN]._cap.activated.emit(2)
    assert session.state.tool_styles[Tool.PEN].cap == "square"
    assert not session.can_undo


def test_fill_rule_only_for_paths_and_composites():
    session, panel = _panel()
    rect = shapes.add_rectangle(session, (0, 0), (10, 10))
    path = shapes.add_path(session, [(0, 0), (10, 10), (20, 0)])
    selection.set_selection(session, {rect})
    assert not panel._style.form.isRowVisible(panel._style._fill_rule)
    selection.set_selection(session, {rect, path})
    assert panel._style.form.isRowVisible(panel._style._fill_rule)


def test_selected_group_shows_heading_bounds_and_its_opacity():
    from presstoshape.editing.operations import groups

    session, panel = _panel()
    first = shapes.add_rectangle(session, (0, 0), (10, 10))
    second = shapes.add_rectangle(session, (20, 0), (30, 10))
    selection.set_selection(session, {first, second})
    groups.group(session)
    assert panel._heading.text() == "Group of 2 objects"
    assert panel._form.isRowVisible(panel._spins["width"])
    assert panel._spins["width"].px() == pytest.approx(30)
    panel._spins["width"].set_px(1)
    panel._spins["width"].setValue(60)
    (group,) = all_shapes(session)
    assert group.children[1].x + group.children[1].width == pytest.approx(60)
    panel._style._opacity.box.setValue(40)
    (group,) = all_shapes(session)
    assert group.opacity == pytest.approx(0.4) and group.children[0].style.opacity == 1
    assert panel._style._opacity.slider.value() == 40


def test_a_gradient_shows_as_a_gradient_and_refresh_stays_silent(editor):
    from presstoshape.models.shapes import GradientStop, LinearGradient

    widget, changes = editor
    gradient = LinearGradient(0, 0, 1, 0, (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff", 0.5)))
    widget.refresh(Style(fill=gradient, stroke=gradient, fill_opacity=0.5))
    assert changes == []
    for row in (widget._fill, widget._stroke):
        assert row.check.isChecked() and row.button.isEnabled()
        assert "qlineargradient" in row.button.styleSheet() and "rgba(0, 0, 255, 128)" in row.button.styleSheet()
        assert row.button.color == "#ff0000" and row.button.toolTip()
    widget.refresh(Style(fill="#00ff00"))
    assert "qlineargradient" not in widget._fill.button.styleSheet() and widget._fill.button.toolTip() == ""
    assert changes == []


def test_picking_a_colour_on_a_gradient_swatch_reports_the_flat_colour(editor):
    from presstoshape.models.shapes import GradientStop, LinearGradient

    widget, changes = editor
    widget.refresh(Style(fill=LinearGradient(0, 0, 1, 0, (GradientStop(0, "#ff0000"), GradientStop(1, "#0000ff")))))
    widget._fill.button.color_picked.emit("#123456")
    widget._fill.check.setChecked(False)
    assert changes == [{"fill": "#123456"}, {"fill": None}]
