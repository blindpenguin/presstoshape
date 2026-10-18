import sys
import tempfile
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from presstoshape import icons
from presstoshape.editing import queries
from presstoshape.editing.operations import composites, documents, selection, shapes
from presstoshape.editing.session import Session
from presstoshape.models.shapes import CompositeShape
from presstoshape.version import app_version
from presstoshape.views import theme, window_placement
from presstoshape.views.app_settings import open_settings
from presstoshape.views.icon_engine import icon
from presstoshape.views.main_window import MainWindow


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

    def run(self, *, screenshot_path: Path | None = None, self_test: bool = False) -> int:
        """`screenshot_path` is a dev-only hook: render once, save a PNG and exit — see scripts/screenshot_app.py.
        `self_test` checks that a (packaged) build works end to end and returns 0 or 1 — see `_self_test`."""

        _set_surface_format()
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("PressToShape")
        app.setWindowIcon(icon(icons.APP))
        theme.apply(app)

        if self_test or screenshot_path is not None:
            window = MainWindow(self.session)
            window.resize(*window_placement.DEFAULT_SIZE)
            window.show()
        else:
            settings = open_settings()
            window = MainWindow(self.session, settings)
            window_placement.show(window, settings)

        if self_test:
            return _run_self_test(app, self.session, window)

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


def _run_self_test(app: QApplication, session: Session, window: MainWindow) -> int:
    """Exit code 0 or 1; the outcome also goes to a log in the temp dir, since windowed builds have no console."""
    log = Path(tempfile.gettempdir()) / "presstoshape-self-test.log"
    try:
        _self_test(app, session, window)
    except Exception as error:  # noqa: BLE001 - any failure means the build is broken
        traceback.print_exc()
        outcome = f"FAIL {type(error).__name__}: {error}"
    else:
        outcome = "OK"
    window.close_without_prompt()
    with log.open("a", encoding="utf-8") as file:
        file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} PressToShape {app_version()} self-test {outcome}\n")
    print(f"self-test {outcome}", file=sys.stderr)
    return 0 if outcome == "OK" else 1


def _self_test(app: QApplication, session: Session, window: MainWindow) -> None:
    """Exercises what a broken bundle would miss: assets, Skia rendering, path ops and SVG round trips."""
    for name, path in vars(icons).items():
        if isinstance(path, Path) and not name.startswith("_"):
            if not path.is_file():
                raise RuntimeError(f"icon {name} missing: {path}")
            if icon(path).pixmap(32).isNull():
                raise RuntimeError(f"icon {name} doesn't render: {path}")

    square = shapes.add_rectangle(session, (60, 60), (260, 220))
    circle = shapes.add_ellipse(session, (180, 140), (340, 300))
    selection.set_selection(session, {square, circle})
    composites.make_composite(session, "subtract")
    shapes.add_path(session, [(40, 330), (140, 250), (240, 360), (360, 300)])
    shapes.add_text(session, (390, 90), "PressToShape")
    count = len(queries.pickable_shapes(session.state))

    with tempfile.TemporaryDirectory() as folder:
        svg_path, png_path = str(Path(folder) / "test.svg"), Path(folder) / "test.png"
        if not documents.save_file(session, svg_path):
            raise RuntimeError(f"saving SVG failed: {session.state.status_message}")
        if not documents.open_file(session, svg_path):
            raise RuntimeError(f"opening SVG failed: {session.state.status_message}")
        reopened = queries.pickable_shapes(session.state)
        if len(reopened) != count or not any(isinstance(shape, CompositeShape) for shape in reopened):
            raise RuntimeError("SVG round trip lost shapes or the composite")
        if not documents.export_png(session, str(png_path), 1.0) or png_path.stat().st_size == 0:
            raise RuntimeError(f"PNG export failed: {session.state.status_message}")

    window.canvas.center_artboard()
    app.processEvents()
    image = window.grab().toImage()
    sampled = {image.pixel(x, y) for x in range(0, image.width(), 7) for y in range(0, image.height(), 7)}
    if len(sampled) < 8:
        raise RuntimeError(f"window looks blank ({len(sampled)} colors)")
