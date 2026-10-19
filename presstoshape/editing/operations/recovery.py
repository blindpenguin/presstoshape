"""Crash recovery snapshots: one per running PressToShape, in a recovery folder of their own.

A snapshot is `<run id>.p2s` (written like Save writes .p2s files, with a small preview) plus `<run id>.json`
(where the document came from and when the snapshot was taken). The views decide when to write and which runs
are still alive; this module only handles the files.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from presstoshape.editing.operations.documents import (
    apply_saved_state,
    preview_png,
    replace_document,
    saved_state,
    write_atomically,
)
from presstoshape.editing.session import Session
from presstoshape.formats import p2s
from presstoshape.geometry.boxes import Point
from presstoshape.i18n import _
from presstoshape.models.app_state import RecoveredFrom
from presstoshape.version import app_version

_DOCUMENT_SUFFIX = ".p2s"
_INFO_SUFFIX = ".json"
_PREVIEW_SIDE = 128
_MAX_INFO_BYTES = 64 * 1024


@dataclass(frozen=True)
class Snapshot:
    run_id: str
    document: Path
    # The file the document came from; None if it was never saved.
    original_path: str | None
    # Seconds since the epoch.
    saved_at: float
    # Its metadata or document can't be read; it can only be discarded.
    damaged: bool = False

    @property
    def name(self) -> str:
        return Path(self.original_path).name if self.original_path else ""


def _files(folder: Path, run_id: str) -> tuple[Path, Path]:
    return folder / f"{run_id}{_DOCUMENT_SUFFIX}", folder / f"{run_id}{_INFO_SUFFIX}"


def write_snapshot(session: Session, folder: Path, run_id: str, view_center: Point | None) -> None:
    """Writes the current document as this run's snapshot. Changes nothing in the session; raises OSError."""
    state = session.state
    original = state.file_path or (state.recovered.original_path if state.recovered else None)
    document_path, info_path = _files(folder, run_id)
    data = p2s.write_p2s(
        state.document, saved_state(state, view_center), preview_png(state.document, _PREVIEW_SIDE), app_version()
    )
    write_atomically(document_path, data)
    info = {"original_path": original, "saved_at": time.time(), "app_version": app_version()}
    write_atomically(info_path, json.dumps(info).encode("utf-8"))


def discard_snapshot(folder: Path, run_id: str) -> None:
    for path in _files(folder, run_id):
        path.unlink(missing_ok=True)


def _read_info(path: Path) -> tuple[str | None, float] | None:
    """(original path, time) from a metadata file, or None if it isn't trustworthy."""
    try:
        if path.stat().st_size > _MAX_INFO_BYTES:
            return None
        info = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(info, dict):
        return None
    original, saved_at = info.get("original_path"), info.get("saved_at")
    if original is not None and not isinstance(original, str):
        return None
    if isinstance(saved_at, bool) or not isinstance(saved_at, (int, float)):
        return None
    return original, float(saved_at)


def find_snapshots(folder: Path, is_running: Callable[[str], bool]) -> list[Snapshot]:
    """Snapshots of runs that aren't running any more (crashed), newest first."""
    if not folder.is_dir():
        return []
    snapshots = []
    for document in folder.glob(f"*{_DOCUMENT_SUFFIX}"):
        run_id = document.stem
        if is_running(run_id):
            continue
        info = _read_info(folder / f"{run_id}{_INFO_SUFFIX}")
        if info is None:
            snapshots.append(Snapshot(run_id, document, None, document.stat().st_mtime, damaged=True))
            continue
        try:
            p2s.read_p2s(document.read_bytes())
        except (OSError, ValueError):
            snapshots.append(Snapshot(run_id, document, info[0], info[1], damaged=True))
            continue
        snapshots.append(Snapshot(run_id, document, *info))
    return sorted(snapshots, key=lambda snapshot: snapshot.saved_at, reverse=True)


def adopt(folder: Path, snapshot: Snapshot, run_id: str) -> Snapshot:
    """Makes a crashed run's snapshot this run's own, so it's kept and cleaned up like a fresh one."""
    for source, target in zip(_files(folder, snapshot.run_id), _files(folder, run_id)):
        if source.exists():
            source.replace(target)
    return Snapshot(run_id, _files(folder, run_id)[0], snapshot.original_path, snapshot.saved_at, snapshot.damaged)


def recover(session: Session, snapshot: Snapshot) -> bool:
    """Opens a snapshot as an unsaved document marked as recovered; its first save is a Save As."""
    name = snapshot.name or _("Untitled")
    try:
        document, saved = p2s.read_p2s(snapshot.document.read_bytes())
    except (OSError, ValueError) as error:
        session.state.status_message = _("Could not recover {name}: {error}").format(name=name, error=error)
        session.notify()
        return False
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(snapshot.saved_at))
    replace_document(session, document, None, _("Recovered {name} (from {time})").format(name=name, time=when))
    state = session.state
    apply_saved_state(state, saved)
    state.dirty = True
    state.recovered = RecoveredFrom(snapshot.original_path, snapshot.saved_at)
    session.notify()
    return True


def report_problem(session: Session, error: OSError) -> None:
    """Status message for a snapshot that couldn't be written; recovery keeps trying."""
    session.state.status_message = _("Couldn't save recovery data: {error}").format(error=error)
    session.notify()
