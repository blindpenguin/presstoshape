"""A real crash: a child process with unsaved changes writes its snapshot and dies without cleaning up."""

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations import recovery
from presstoshape.editing.session import Session
from presstoshape.views.main_window import MainWindow
from presstoshape.views.recovery_keeper import RecoveryKeeper
from tests.helpers import all_shapes

ROOT = Path(__file__).resolve().parents[2]
CHILD = """
import os, sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, QSettings
from presstoshape.editing.operations import documents, shapes
from presstoshape.editing.session import Session
from presstoshape.views.recovery_keeper import RecoveryKeeper

app = QCoreApplication([])
folder = Path(sys.argv[1])
session = Session()
documents.new_document(session, documents.DocumentSetup(210, 297, "mm", 300))
shapes.add_rectangle(session, (10, 20), (110, 220))
shapes.add_ellipse(session, (300, 300), (500, 400))
settings = QSettings(str(folder / "settings.ini"), QSettings.Format.IniFormat)
keeper = RecoveryKeeper(session, folder / "recovery", lambda: (1.0, 2.0), settings)
keeper._write()
print(keeper.run_id, flush=True)
os._exit(1)
"""


def _expected() -> Session:
    from presstoshape.editing.operations import documents, shapes

    session = Session()
    documents.new_document(session, documents.DocumentSetup(210, 297, "mm", 300))
    shapes.add_rectangle(session, (10, 20), (110, 220))
    shapes.add_ellipse(session, (300, 300), (500, 400))
    return session


def test_a_killed_run_is_offered_and_recovered_exactly(tmp_path):
    child = subprocess.run(
        [sys.executable, "-c", CHILD, str(tmp_path)],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT), "QT_QPA_PLATFORM": "offscreen"},
        capture_output=True,
        text=True,
        timeout=60,
    )
    crashed_run = child.stdout.strip()
    assert child.returncode == 1 and crashed_run, child.stderr
    folder = tmp_path / "recovery"
    assert (folder / f"{crashed_run}.lock").exists()

    QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    session = Session()
    keeper = RecoveryKeeper(session, folder, lambda: (0.0, 0.0), settings)
    (snapshot,) = recovery.find_snapshots(folder, keeper.is_running)
    assert snapshot.run_id == crashed_run
    assert recovery.recover(session, recovery.adopt(folder, snapshot, keeper.run_id))
    assert all_shapes(session) == all_shapes(_expected())
    assert (session.state.document.unit, session.state.dirty) == ("mm", True)
    keeper.finish()

    window = MainWindow(session, settings, tmp_path / "other-recovery", tmp_path / "swatches.json")
    window.refresh()
    assert window.windowTitle().startswith("Untitled (recovered)")
    window.close_without_prompt()
