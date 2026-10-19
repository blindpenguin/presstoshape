"""Keeps this run's crash recovery snapshot up to date.

One rule: while the document has unsaved changes, its snapshot is at most one interval old; without unsaved
changes (saved, new, opened, discarded) or with recovery off, there is none. A lock file named after the run tells
later starts whether the run is still going or crashed.
"""

import uuid
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QSettings, QTimer

from presstoshape.editing.operations import recovery
from presstoshape.editing.session import Session
from presstoshape.geometry.boxes import Point
from presstoshape.views import app_settings

MINUTE_MS = 60_000


class RecoveryKeeper(QObject):
    def __init__(
        self,
        session: Session,
        folder: Path,
        view_center: Callable[[], Point],
        settings: QSettings,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._session = session
        self._view_center = view_center
        self._settings = settings
        self.folder = folder
        self.run_id = uuid.uuid4().hex
        self._written_revision: int | None = None
        self._failing = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._write)
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            # Without a folder there's no recovery this run; the app works as before.
            self._enabled = False
            recovery.report_problem(session, error)
            return
        self._enabled = True
        self._lock = QLockFile(str(folder / f"{self.run_id}.lock"))
        # Only a dead owner makes a lock stale, never its age: long sessions stay protected.
        self._lock.setStaleLockTime(0)
        self._lock.tryLock(0)

    def is_running(self, run_id: str) -> bool:
        """Whether that run is this one or still holds its lock; a crashed run's lock can be taken."""
        if run_id == self.run_id:
            return True
        other = QLockFile(str(self.folder / f"{run_id}.lock"))
        other.setStaleLockTime(0)
        if other.tryLock(0):
            other.unlock()
            return False
        return other.error() == QLockFile.LockError.LockFailedError

    def refresh(self) -> None:
        if not self._enabled:
            return
        interval = app_settings.recovery_interval(self._settings)
        if interval == 0 or not self._session.state.dirty:
            self._timer.stop()
            self._discard()
            return
        if self._session.revision != self._written_revision and not self._timer.isActive():
            self._timer.start(interval * MINUTE_MS)

    def _write(self) -> None:
        if not self._session.state.dirty or self._session.revision == self._written_revision:
            return
        revision = self._session.revision
        try:
            recovery.write_snapshot(self._session, self.folder, self.run_id, self._view_center())
        except OSError as error:
            if not self._failing:
                self._failing = True
                recovery.report_problem(self._session, error)
            self.refresh()
            return
        self._failing = False
        self._written_revision = revision
        # Changes made since the timer started get the next interval.
        self.refresh()

    def _discard(self) -> None:
        if self._written_revision is None and not (self.folder / f"{self.run_id}.p2s").exists():
            return
        try:
            recovery.discard_snapshot(self.folder, self.run_id)
        except OSError:
            # A snapshot that can't be deleted is offered once more after the next start; nothing to do now.
            pass
        self._written_revision = None

    def finish(self) -> None:
        """Clean quit: this run's snapshot and lock go away."""
        if not self._enabled:
            return
        self._timer.stop()
        self._discard()
        self._lock.unlock()
        self._enabled = False
