"""New, open, save and PNG export. Paths come from the view's dialogs; I/O errors end up in the status bar.
The format follows the file extension: .p2s is PressToShape's own format, anything else is SVG."""

import os
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from presstoshape.editing import containers, queries
from presstoshape.editing.operations.view import MAX_ZOOM, MIN_ZOOM
from presstoshape.editing.session import Session
from presstoshape.formats import p2s, svg
from presstoshape.formats.p2s import P2sError, SavedState
from presstoshape.geometry import units
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState, Document, Unit
from presstoshape.models.document_presets import DEFAULT
from presstoshape.render import export
from presstoshape.version import app_version

NATIVE_SUFFIX = ".p2s"
PREVIEW_SIDE = 256


@dataclass(frozen=True)
class DocumentSetup:
    """Size of a new document in `unit` (portrait or landscape as given), plus its resolution."""

    width: float
    height: float
    unit: Unit
    dpi: float


DEFAULT_SETUP = DocumentSetup(DEFAULT.width, DEFAULT.height, DEFAULT.unit, DEFAULT.dpi)


def setup_problem(setup: DocumentSetup) -> str | None:
    """Why a setup can't become a document (for the dialog to show), or None."""
    if setup.unit not in units.UNITS:
        return _("Unknown unit {unit}").format(unit=setup.unit)
    if not units.MIN_DPI <= setup.dpi <= units.MAX_DPI:
        return _("DPI must be between {minimum} and {maximum}").format(
            minimum=round(units.MIN_DPI), maximum=round(units.MAX_DPI)
        )
    for side in (setup.width, setup.height):
        pixels = units.to_px(side, setup.unit, setup.dpi)
        if pixels < 1:
            return _("Width and height must be at least 1 px")
        if pixels > units.MAX_DOCUMENT_PX:
            return _("Width and height can be at most {maximum} px at this DPI").format(
                maximum=round(units.MAX_DOCUMENT_PX)
            )
    return None


def is_native(path: str) -> bool:
    return Path(path).suffix.lower() == NATIVE_SUFFIX


def _reset(session: Session, document: Document, path: str | None, message: str) -> None:
    state = session.state
    state.document = document
    state.file_path = path
    state.dirty = False
    state.selection = set()
    state.node_selection = frozenset()
    state.edit_path = ()
    state.selected_layer_index = len(document.layers) - 1
    state.restore_view_center = None
    state.status_message = message
    session.clear_history()
    session.notify()


def new_document(session: Session, setup: DocumentSetup = DEFAULT_SETUP) -> None:
    """Replaces the document with an empty one of this size. Not an undo step; raises ValueError for setups
    setup_problem() rejects (the dialog never offers them)."""
    problem = setup_problem(setup)
    if problem is not None:
        raise ValueError(problem)
    width, height = (units.to_px(side, setup.unit, setup.dpi) for side in (setup.width, setup.height))
    document = Document(width=width, height=height, unit=setup.unit, dpi=setup.dpi)
    _reset(session, document, None, _("New document"))


def _apply_saved_state(state: AppState, saved: SavedState) -> None:
    """Working state from a .p2s file; ids that no longer match the document are dropped, not trusted."""
    state.tool_styles.update(saved.tool_styles)
    if saved.font_size is not None:
        state.font_size = saved.font_size
    if saved.new_part_mode is not None:
        state.new_part_mode = saved.new_part_mode
    if saved.zoom_percent is not None:
        state.zoom_percent = max(MIN_ZOOM, min(MAX_ZOOM, saved.zoom_percent))
    if saved.selected_layer is not None and saved.selected_layer < len(state.document.layers):
        state.selected_layer_index = saved.selected_layer
    state.edit_path = saved.edit_path
    state.edit_path = containers.valid_edit_path(state)
    pickable = {shape.id for shape in queries.pickable_shapes(state)}
    state.selection = set(saved.selection) & pickable
    state.restore_view_center = saved.view_center


def open_file(session: Session, path: str) -> bool:
    name = Path(path).name
    try:
        if is_native(path):
            document, saved = p2s.read_p2s(Path(path).read_bytes())
            notes: list[str] = []
        else:
            document, notes = svg.read_svg_with_notes(Path(path).read_text(encoding="utf-8"))
            saved = None
    except (OSError, ValueError, ET.ParseError) as error:
        # P2sError is a ValueError, with a message written for this status line.
        session.state.status_message = _("Could not open {name}: {error}").format(name=name, error=error)
        session.notify()
        return False
    message = _("Opened {name}").format(name=name)
    if notes:
        message += ". " + ". ".join(dict.fromkeys(notes))
    _reset(session, document, path, message)
    if saved is not None:
        _apply_saved_state(session.state, saved)
        session.notify()
    return True


def _saved_state(state: AppState, view_center: tuple[float, float] | None) -> SavedState:
    return SavedState(
        zoom_percent=state.zoom_percent,
        view_center=view_center,
        tool_styles=dict(state.tool_styles),
        font_size=state.font_size,
        new_part_mode=state.new_part_mode,
        selection=frozenset(state.selection),
        selected_layer=state.selected_layer_index,
        edit_path=containers.valid_edit_path(state),
    )


def _preview(document: Document) -> bytes | None:
    scale = min(1.0, PREVIEW_SIDE / max(document.width, document.height))
    return export.render_png(document, scale)


def _write_atomically(target: Path, data: bytes) -> None:
    """Writes beside the target and swaps it in only when complete, so a failed save never damages the file."""
    handle = tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(handle.name, target)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def save_file(session: Session, path: str | None = None, view_center: tuple[float, float] | None = None) -> bool:
    """Saves to `path`, or the current file, in the format its extension names. `view_center` (doc point at the
    viewport center) is stored in .p2s files. Returns False if there's no target or writing failed."""
    state = session.state
    target = path or state.file_path
    if target is None:
        return False
    name = Path(target).name
    native = is_native(target)
    try:
        if native:
            saved = _saved_state(state, view_center)
            data = p2s.write_p2s(state.document, saved, _preview(state.document), app_version())
        else:
            data = svg.write_svg(state.document).encode("utf-8")
        _write_atomically(Path(target), data)
    except (OSError, P2sError) as error:
        state.status_message = _("Could not save {name}: {error}").format(name=name, error=error)
        session.notify()
        return False
    state.file_path = target
    state.dirty = False
    state.status_message = _("Saved {name}").format(name=name)
    if not native and not state.svg_hint_shown:
        state.svg_hint_shown = True
        state.status_message = _(
            "Saved {name} (view, tool settings and selection are only kept in .p2s files)"
        ).format(name=name)
    session.notify()
    return True


def export_png(session: Session, path: str, scale: float) -> bool:
    """Writes the artboard as PNG. Not an edit: undo history and the dirty flag are untouched."""
    state = session.state
    state.export.scale = scale
    name = Path(path).name
    data = export.render_png(state.document, scale, state.document.dpi * scale)
    try:
        if data is None:
            raise ValueError(_("the image is too large to render"))
        Path(path).write_bytes(data)
    except (OSError, ValueError) as error:
        state.status_message = _("Export failed: {error}").format(error=error)
        session.notify()
        return False
    width, height = export.export_size(state.document, scale)
    state.status_message = _("Exported {name} ({width} × {height} px)").format(name=name, width=width, height=height)
    session.notify()
    return True
