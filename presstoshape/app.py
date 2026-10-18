import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from presstoshape.editing.session import Session
from presstoshape.views import theme
from presstoshape.views.main_window import MainWindow

_WINDOW_SIZE = (1100, 700)


def _set_surface_format() -> None:
    """Must run before QApplication exists; the canvas's Skia GL context inherits it."""
    fmt = QSurfaceFormat()
    fmt.setStencilBufferSize(8)
    if sys.platform == "darwin":
        # macOS only offers legacy 2.1 or 4.1 core.
        fmt.setVersion(4, 1)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    QSurfaceFormat.setDefaultFormat(fmt)


class App:
    def __init__(self) -> None:
        self.session = Session()

    def run(self, *, screenshot_path: Path | None = None) -> int:
        """`screenshot_path` is a dev-only hook: render once, save a PNG and exit — see scripts/screenshot_app.py."""

        _set_surface_format()
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("PressToShape")
        theme.apply(app)

        window = MainWindow(self.session)
        window.resize(*_WINDOW_SIZE)
        window.show()

        if screenshot_path is not None:
            app.processEvents()
            window.canvas.center_artboard()
            app.processEvents()
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            window.grab().save(str(screenshot_path))
            window.close_without_prompt()
            return 0

        # Deferred until the window has its real size, otherwise centering uses the pre-layout viewport.
        QTimer.singleShot(0, window.canvas.center_artboard)
        return app.exec()
