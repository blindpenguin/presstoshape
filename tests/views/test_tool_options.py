from PySide6.QtWidgets import QApplication, QWidget

from presstoshape.editing.operations import view
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool
from presstoshape.views.actions import AppActions
from presstoshape.views.tool_options_view import ToolOptionsPanel


def test_pencil_smoothing_slider_follows_and_sets_the_state():
    QApplication.instance() or QApplication([])
    session = Session()
    actions = AppActions(QWidget(), session, {})
    panel = ToolOptionsPanel(session, actions)
    session.subscribe(lambda: panel.refresh(session.state))
    view.select_tool(session, Tool.PENCIL)
    assert panel._smoothing.value() == 50 and panel._smoothing_value.text() == "50"
    panel._smoothing.setValue(70)
    assert session.state.pencil_smoothing == 70 and panel._smoothing_value.text() == "70"
    view.set_pencil_smoothing(session, 20)
    assert panel._smoothing.value() == 20
