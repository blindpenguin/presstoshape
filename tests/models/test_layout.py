from dataclasses import replace

from presstoshape.editing.session import Session
from presstoshape.models.app_state import AppState
from presstoshape.models.layout import GridSettings, Guide, SnapSettings, ViewOptions


def test_view_and_snap_defaults():
    state = AppState()
    assert state.view == ViewOptions(show_rulers=True, show_grid=False, show_guides=True, lock_guides=False)
    assert state.snapping == SnapSettings()
    assert state.snapping.enabled and not state.snapping.grid and state.snapping.distance_px == 8
    assert state.align_reference == "selection"


def test_documents_start_without_guides_or_own_grid():
    document = AppState().document
    assert document.guides == () and document.grid is None


def test_guides_and_grid_are_undone_with_the_document():
    session = Session()
    with session.edit("Add guide"):
        session.state.document = replace(
            session.state.document, guides=(Guide(1, "vertical", 50.0),), grid=GridSettings(20.0, 4)
        )
    session.undo()
    assert session.state.document.guides == () and session.state.document.grid is None
    session.redo()
    assert session.state.document.guides == (Guide(1, "vertical", 50.0),)
