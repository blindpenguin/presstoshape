import struct

import pytest

from presstoshape.editing.operations import composites, documents, edit_mode, selection, shapes, view
from presstoshape.editing.session import Session
from presstoshape.formats import p2s
from presstoshape.models.app_state import Tool
from tests.helpers import all_shapes


def test_save_and_open_roundtrip(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    path = tmp_path / "a.svg"
    assert documents.save_file(session, str(path))
    assert not session.state.dirty and session.state.file_path == str(path)

    other = Session()
    assert documents.open_file(other, str(path))
    assert all_shapes(other) == all_shapes(session)
    assert not other.can_undo


def test_save_without_path_returns_false():
    assert not documents.save_file(Session())


def test_open_bad_file_reports_and_keeps_document(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    bad = tmp_path / "bad.svg"
    bad.write_text("<svg")
    assert not documents.open_file(session, str(bad))
    assert "Could not open" in session.state.status_message
    assert len(all_shapes(session)) == 1


# --- native .p2s ------------------------------------------------------------------------------------


def _drawing_session() -> tuple[Session, int, int]:
    session = Session()
    bottom = shapes.add_rectangle(session, (0, 0), (100, 80))
    top = shapes.add_ellipse(session, (50, 40), (150, 120))
    selection.set_selection(session, {bottom, top})
    composites.make_composite(session, "subtract")
    (composite_id,) = session.state.selection
    edit_mode.enter(session, composite_id)
    selection.set_selection(session, {top})
    view.set_zoom(session, 250)
    view.set_tool_style(session, Tool.RECTANGLE, fill="#123456")
    view.set_font_size(session, 40)
    composites.set_new_part_mode(session, "intersect")
    return session, composite_id, top


def test_p2s_round_trip_restores_document_and_working_state(tmp_path):
    session, composite_id, top = _drawing_session()
    path = str(tmp_path / "drawing.p2s")
    assert documents.save_file(session, path, view_center=(75.0, 60.5))
    assert not session.state.dirty and session.state.status_message == "Saved drawing.p2s"

    other = Session()
    assert documents.open_file(other, path)
    state = other.state
    assert all_shapes(other) == all_shapes(session)
    assert state.edit_path == (composite_id,) and state.selection == {top}
    assert state.zoom_percent == 250 and state.restore_view_center == (75.0, 60.5)
    assert state.tool_styles[Tool.RECTANGLE].fill == "#123456"
    assert state.font_size == 40 and state.new_part_mode == "intersect"
    assert not other.can_undo and not state.dirty and state.file_path == path


def test_p2s_file_contains_a_small_preview(tmp_path):
    session, _, _ = _drawing_session()
    path = tmp_path / "drawing.p2s"
    documents.save_file(session, str(path))
    preview = p2s.read_preview(path.read_bytes())
    assert preview is not None and preview.startswith(b"\x89PNG")
    width, height = struct.unpack(">II", preview[16:24])
    assert max(width, height) <= documents.PREVIEW_SIDE


def test_stale_selection_and_edit_path_are_dropped(tmp_path):
    session, composite_id, top = _drawing_session()
    path = tmp_path / "drawing.p2s"
    saved = p2s.SavedState(selection=frozenset({999, top}), edit_path=(composite_id, 777), zoom_percent=100_000)
    path.write_bytes(p2s.write_p2s(session.state.document, saved, None, "test"))
    other = Session()
    documents.open_file(other, str(path))
    assert other.state.edit_path == (composite_id,)
    assert other.state.selection == {top}
    assert other.state.zoom_percent == view.MAX_ZOOM


def test_extension_decides_the_format(tmp_path):
    session, _, _ = _drawing_session()
    documents.save_file(session, str(tmp_path / "a.P2S"))
    documents.save_file(session, str(tmp_path / "b.svg"))
    assert (tmp_path / "a.P2S").read_bytes().startswith(b"PK")
    assert (tmp_path / "b.svg").read_text().lstrip().startswith("<?xml")


def test_opened_svg_keeps_saving_svg(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    path = tmp_path / "keep.svg"
    documents.save_file(session, str(path))
    other = Session()
    documents.open_file(other, str(path))
    shapes.add_rectangle(other, (20, 20), (30, 30))
    assert documents.save_file(other)
    assert path.read_text().count("<rect") == 2


def test_svg_hint_is_shown_once_per_session(tmp_path):
    session = Session()
    documents.save_file(session, str(tmp_path / "one.svg"))
    assert "only kept in .p2s" in session.state.status_message
    documents.save_file(session, str(tmp_path / "two.svg"))
    assert session.state.status_message == "Saved two.svg"


def test_failed_save_leaves_the_old_file_intact(tmp_path, monkeypatch):
    session, _, _ = _drawing_session()
    path = tmp_path / "drawing.p2s"
    documents.save_file(session, str(path))
    before = path.read_bytes()

    def broken_replace(source, target):
        raise OSError("disk full")

    monkeypatch.setattr(documents.os, "replace", broken_replace)
    shapes.add_rectangle(session, (200, 200), (210, 210))
    assert not documents.save_file(session, str(path))
    assert "disk full" in session.state.status_message
    assert path.read_bytes() == before
    assert sorted(item.name for item in tmp_path.iterdir()) == ["drawing.p2s"]


def test_broken_p2s_reports_and_keeps_the_document(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    bad = tmp_path / "bad.p2s"
    bad.write_bytes(b"definitely not a zip")
    assert not documents.open_file(session, str(bad))
    assert session.state.status_message == "Could not open bad.p2s: not a PressToShape file"
    assert len(all_shapes(session)) == 1


# --- new documents with a setup -------------------------------------------------------------


def test_new_document_from_a_print_setup():
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    documents.new_document(session, documents.DocumentSetup(210, 297, "mm", 300))
    document = session.state.document
    assert (document.width, document.height) == pytest.approx((2480.31, 3507.87), abs=0.01)
    assert (document.unit, document.dpi) == ("mm", 300)
    assert not session.state.dirty and not session.can_undo
    assert all(not layer.shapes for layer in document.layers)


def test_default_setup_is_the_old_default():
    session = Session()
    documents.new_document(session)
    document = session.state.document
    assert (document.width, document.height, document.unit, document.dpi) == (600, 400, "px", 96)


def test_invalid_setups_are_refused():
    for setup in (
        documents.DocumentSetup(0.1, 100, "px", 96),
        documents.DocumentSetup(100, 100, "px", 0),
        documents.DocumentSetup(2, 2, "km", 96),
        documents.DocumentSetup(1000, 1000, "in", 300),
    ):
        assert documents.setup_problem(setup) is not None
        with pytest.raises(ValueError):
            documents.new_document(Session(), setup)


# --- backups and recovered documents ---------------------------------------------------------


def test_saving_over_a_file_keeps_one_backup(tmp_path):
    session = Session()
    path = tmp_path / "poster.p2s"
    assert documents.save_file(session, str(path), keep_backup=True)
    assert not documents.backup_path(path).exists()
    first = path.read_bytes()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    assert documents.save_file(session, keep_backup=True)
    backup = documents.backup_path(path)
    assert backup.name == "poster.backup.p2s" and backup.read_bytes() == first
    second = path.read_bytes()
    shapes.add_rectangle(session, (20, 0), (30, 10))
    documents.save_file(session, keep_backup=True)
    assert backup.read_bytes() == second


def test_no_backup_when_turned_off(tmp_path):
    session = Session()
    path = tmp_path / "logo.svg"
    documents.save_file(session, str(path))
    documents.save_file(session)
    assert not documents.backup_path(path).exists()


def test_failed_backup_still_saves_with_a_note(tmp_path, monkeypatch):
    session = Session()
    path = tmp_path / "logo.svg"
    documents.save_file(session, str(path))
    shapes.add_rectangle(session, (0, 0), (10, 10))

    def refuse(*args, **kwargs):
        raise OSError("read-only")

    monkeypatch.setattr(documents.shutil, "copy2", refuse)
    assert documents.save_file(session, keep_backup=True)
    assert "<rect" in path.read_text()
    assert "no backup" in session.state.status_message


def test_failed_write_leaves_file_and_backup_alone(tmp_path, monkeypatch):
    session = Session()
    path = tmp_path / "poster.p2s"
    documents.save_file(session, str(path))
    shapes.add_rectangle(session, (0, 0), (10, 10))
    documents.save_file(session, keep_backup=True)
    file_bytes, backup_bytes = path.read_bytes(), documents.backup_path(path).read_bytes()

    def fail(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(documents.os, "fsync", fail)
    shapes.add_rectangle(session, (20, 0), (30, 10))
    assert not documents.save_file(session, keep_backup=True)
    assert (path.read_bytes(), documents.backup_path(path).read_bytes()) == (file_bytes, backup_bytes)


def test_recovered_marker_is_cleared_by_saving_new_and_open(tmp_path):
    from presstoshape.models.app_state import RecoveredFrom

    session = Session()
    session.state.recovered = RecoveredFrom(None, 0.0)
    documents.save_file(session, str(tmp_path / "a.p2s"))
    assert session.state.recovered is None
    session.state.recovered = RecoveredFrom(None, 0.0)
    documents.new_document(session)
    assert session.state.recovered is None
    session.state.recovered = RecoveredFrom(None, 0.0)
    documents.open_file(session, str(tmp_path / "a.p2s"))
    assert session.state.recovered is None


def test_pencil_smoothing_is_kept_in_p2s_files(tmp_path):
    from presstoshape.editing.operations import view as view_operations

    session = Session()
    view_operations.set_pencil_smoothing(session, 85)
    documents.save_file(session, str(tmp_path / "a.p2s"))
    other = Session()
    documents.open_file(other, str(tmp_path / "a.p2s"))
    assert other.state.pencil_smoothing == 85


def test_opening_a_lossy_svg_keeps_its_notes_outside_undo(tmp_path):
    target = tmp_path / "lossy.svg"
    target.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="5" height="5" fill="url(#g)"/><image href="x.png" width="1" height="1"/></svg>',
        encoding="utf-8",
    )
    session = Session()
    assert documents.open_file(session, str(target))
    assert session.state.import_notes == ["1 gradient or pattern was painted grey", "1 image was left out"]
    assert session.state.status_message == "Opened lossy.svg with 2 import notes"
    assert not session.can_undo
    view.clear_import_notes(session)
    assert session.state.import_notes == []


def test_clean_files_have_no_import_notes(tmp_path):
    session = Session()
    shapes.add_rectangle(session, (0, 0), (10, 10))
    for name in ("clean.svg", "clean.p2s"):
        documents.save_file(session, str(tmp_path / name))
        reopened = Session()
        reopened.state.import_notes = ["stale"]
        documents.open_file(reopened, str(tmp_path / name))
        assert reopened.state.import_notes == []


def test_an_entered_group_is_entered_again_after_reopening(tmp_path):
    from pathlib import Path

    sample = Path(__file__).resolve().parent.parent / "formats" / "samples" / "v5.p2s"
    target = tmp_path / "grouped.p2s"
    target.write_bytes(sample.read_bytes())
    session = Session()
    assert documents.open_file(session, str(target))
    assert session.state.edit_path == (1,)
    assert session.state.selection == {7}


def test_opening_and_pasting_svg_use_the_active_language(tmp_path):
    from presstoshape import i18n
    from presstoshape.i18n.catalog import Catalog

    text = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><switch>'
        '<text systemLanguage="de" x="0" y="10">Hallo</text><text x="0" y="10">Hello</text></switch></svg>'
    )
    path = tmp_path / "t.svg"
    path.write_text(text, encoding="utf-8")
    try:
        i18n.install(Catalog("de"))
        session = Session()
        assert documents.open_file(session, str(path))
        assert [shape.text for shape in all_shapes(session)] == ["Hallo"]
    finally:
        i18n.install(Catalog("en"))
    session = Session()
    assert documents.open_file(session, str(path))
    assert [shape.text for shape in all_shapes(session)] == ["Hello"]
