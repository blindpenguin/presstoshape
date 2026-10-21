"""New, open, save and PNG export. Paths come from the view's dialogs; I/O errors end up in the status bar.
The format follows the file extension: .p2s is PressToShape's own format, anything else is SVG."""

import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, replace
from pathlib import Path

from presstoshape.editing import containers, queries
from presstoshape.editing.operations.view import MAX_ZOOM, MIN_ZOOM
from presstoshape.editing.session import Session
from presstoshape.formats import p2s, svg
from presstoshape.formats.p2s import P2sError, SavedState
from presstoshape.geometry import units
from presstoshape.i18n import _, ngettext, user_languages
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


def replace_document(session: Session, document: Document, path: str | None, message: str) -> None:
    state = session.state
    state.document = document
    state.file_path = path
    state.dirty = False
    state.recovered = None
    state.selection = set()
    state.node_selection = frozenset()
    state.edit_path = ()
    state.selected_layer_index = len(document.layers) - 1
    state.restore_view_center = None
    state.import_notes = []
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
    replace_document(session, document, None, _("New document"))


def apply_saved_state(state: AppState, saved: SavedState) -> None:
    """Working state from a .p2s file; ids that no longer match the document are dropped, not trusted."""
    state.tool_styles.update(saved.tool_styles)
    shown = {key: getattr(saved, key) for key in ("show_grid", "show_guides", "lock_guides")}
    state.view = replace(state.view, **{key: value for key, value in shown.items() if value is not None})
    if saved.font_size is not None:
        state.font_size = saved.font_size
    if saved.new_part_mode is not None:
        state.new_part_mode = saved.new_part_mode
    if saved.pencil_smoothing is not None:
        state.pencil_smoothing = saved.pencil_smoothing
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
            document, notes = svg.read_svg_with_notes(Path(path).read_text(encoding="utf-8"), user_languages())
            saved = None
    except (OSError, ValueError, ET.ParseError) as error:
        # P2sError is a ValueError, with a message written for this status line.
        session.state.status_message = _("Could not open {name}: {error}").format(name=name, error=error)
        session.notify()
        return False
    if notes:
        message = ngettext(
            "Opened {name} with {count} import note", "Opened {name} with {count} import notes", len(notes)
        ).format(name=name, count=len(notes))
    else:
        message = _("Opened {name}").format(name=name)
    replace_document(session, document, path, message)
    session.state.import_notes = notes
    if saved is not None:
        apply_saved_state(session.state, saved)
        session.notify()
    return True


def saved_state(state: AppState, view_center: tuple[float, float] | None) -> SavedState:
    return SavedState(
        zoom_percent=state.zoom_percent,
        view_center=view_center,
        tool_styles=dict(state.tool_styles),
        font_size=state.font_size,
        new_part_mode=state.new_part_mode,
        pencil_smoothing=state.pencil_smoothing,
        selection=frozenset(state.selection),
        selected_layer=state.selected_layer_index,
        edit_path=containers.valid_edit_path(state),
        show_grid=state.view.show_grid,
        show_guides=state.view.show_guides,
        lock_guides=state.view.lock_guides,
    )


def preview_png(document: Document, side: int = PREVIEW_SIDE) -> bytes | None:
    scale = min(1.0, side / max(document.width, document.height))
    return export.render_png(document, scale)


def backup_path(target: Path) -> Path:
    """`poster.p2s` → `poster.backup.p2s`: keeps the extension, so the backup opens like the file."""
    return target.with_name(f"{target.stem}.backup{target.suffix}")


def write_atomically(target: Path, data: bytes, keep_backup: bool = False) -> bool:
    """Writes beside the target and swaps it in only when complete, so a failed save never damages the file.
    With `keep_backup`, the old file is copied to backup_path() right before the swap (a failed write leaves the
    file and its backup alone). Returns False if a wanted backup couldn't be made; the file is saved anyway."""
    handle = tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False)
    backed_up = True
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if keep_backup and target.is_file():
            try:
                shutil.copy2(target, backup_path(target))
            except OSError:
                backed_up = False
        os.replace(handle.name, target)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise
    return backed_up


def save_file(
    session: Session,
    path: str | None = None,
    view_center: tuple[float, float] | None = None,
    keep_backup: bool = False,
) -> bool:
    """Saves to `path`, or the current file, in the format its extension names. `view_center` (doc point at the
    viewport center) is stored in .p2s files; `keep_backup` keeps the previous file as a backup. Returns False if
    there's no target or writing failed."""
    state = session.state
    target = path or state.file_path
    if target is None:
        return False
    name = Path(target).name
    native = is_native(target)
    try:
        if native:
            saved = saved_state(state, view_center)
            data = p2s.write_p2s(state.document, saved, preview_png(state.document), app_version())
        else:
            data = svg.write_svg(state.document).encode("utf-8")
        backed_up = write_atomically(Path(target), data, keep_backup)
    except (OSError, P2sError) as error:
        state.status_message = _("Could not save {name}: {error}").format(name=name, error=error)
        session.notify()
        return False
    state.file_path = target
    state.dirty = False
    state.recovered = None
    state.status_message = _("Saved {name}").format(name=name)
    if not native and not state.svg_hint_shown:
        state.svg_hint_shown = True
        state.status_message = _(
            "Saved {name} (view, tool settings and selection are only kept in .p2s files)"
        ).format(name=name)
    if not backed_up:
        state.status_message = _("{message} (no backup of the previous version could be made)").format(
            message=state.status_message
        )
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
