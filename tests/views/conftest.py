import os

import pytest
from PySide6.QtCore import QCoreApplication, QEvent

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(autouse=True)
def delete_widgets():
    """Deletes the widgets a test left open while the QApplication still exists; Qt objects destroyed at
    interpreter exit, after it, can crash the process ("pure virtual method called")."""
    yield
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    for widget in app.topLevelWidgets():
        if widget.isVisible():
            widget.close()
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
