"""New, open, save and PNG export. Paths come from the view's dialogs; I/O errors end up in the status bar."""

import xml.etree.ElementTree as ET
from pathlib import Path

from veccy.editing.session import Session
from veccy.formats import svg
from veccy.models.app_state import Document
from veccy.render import export


def _reset(session: Session, document: Document, path: str | None, message: str) -> None:
    state = session.state
    state.document = document
    state.file_path = path
    state.dirty = False
    state.selection = set()
    state.node_selection = frozenset()
    state.selected_layer_index = len(document.layers) - 1
    state.status_message = message
    session.clear_history()
    session.notify()


def new_document(session: Session) -> None:
    _reset(session, Document(), None, "New document")


def open_file(session: Session, path: str) -> bool:
    try:
        document = svg.read_svg(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, ET.ParseError) as error:
        session.state.status_message = f"Could not open {Path(path).name}: {error}"
        session.notify()
        return False
    _reset(session, document, path, f"Opened {Path(path).name}")
    return True


def save_file(session: Session, path: str | None = None) -> bool:
    """Saves to `path`, or the current file. Returns False if there's no target or writing failed."""
    state = session.state
    target = path or state.file_path
    if target is None:
        return False
    try:
        Path(target).write_text(svg.write_svg(state.document), encoding="utf-8")
    except OSError as error:
        state.status_message = f"Could not save {Path(target).name}: {error}"
        session.notify()
        return False
    state.file_path = target
    state.dirty = False
    state.status_message = f"Saved {Path(target).name}"
    session.notify()
    return True


def export_png(session: Session, path: str, scale: float) -> bool:
    """Writes the artboard as PNG. Not an edit: undo history and the dirty flag are untouched."""
    state = session.state
    state.export.scale = scale
    name = Path(path).name
    data = export.render_png(state.document, scale)
    try:
        if data is None:
            raise ValueError("image too large to render")
        Path(path).write_bytes(data)
    except (OSError, ValueError) as error:
        state.status_message = f"Export failed: {error}"
        session.notify()
        return False
    width, height = export.export_size(state.document, scale)
    state.status_message = f"Exported {name} ({width} × {height} px)"
    session.notify()
    return True
