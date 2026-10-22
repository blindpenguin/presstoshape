import logging
import sys
import tempfile
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, QSettings, QTimer, QTranslator
from PySide6.QtGui import QSurfaceFormat
from PySide6.QtWidgets import QApplication

from presstoshape import i18n, icons
from presstoshape.editing import queries
from presstoshape.editing.operations import composites, documents, selection, shapes
from presstoshape.editing.session import Session
from presstoshape.i18n import languages
from presstoshape.models.shapes import CompositeShape
from presstoshape.version import app_version
from presstoshape.views import app_settings, theme, window_placement
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


_log = logging.getLogger(__name__)


def resolve_language(settings: QSettings | None, requested: str | None = None) -> languages.Language:
    """`requested` (a code) if available, else the saved choice, else the system language, else English."""
    available = languages.available_languages(app_settings.translations_folder())
    saved = requested or (app_settings.language(settings) if settings is not None else None)
    code = languages.resolve(saved, QLocale.system().uiLanguages(), available)
    return next(language for language in available if language.code == code)


def qt_translator(code: str) -> QTranslator | None:
    """Qt's own texts (standard buttons, file dialogs) in `code`; None if Qt ships no translation for it."""
    translator = QTranslator()
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale(languages.locale_name(code)), "qtbase", "_", folder):
        return translator
    if code != languages.ENGLISH:
        _log.warning("No Qt translation for %s in %s", code, folder)
    return None


class App:
    def __init__(self, language: str | None = None) -> None:
        """`language` forces a language code (screenshots, self-test); None uses the setting or the system's.
        The language is installed before the Session exists, so the first layer gets a translated name."""
        self._settings = None if language is not None else open_settings()
        self.language = resolve_language(self._settings, language)
        i18n.install(languages.load_catalog(self.language))
        # Number fields follow the interface language (decimal comma in German), not the system locale.
        QLocale.setDefault(QLocale(languages.locale_name(self.language.code)))
        self._qt_translator: QTranslator | None = None
        self.session = Session()

    def run(self, *, screenshot_path: Path | None = None, self_test: bool = False) -> int:
        """`screenshot_path` is a dev-only hook: render once, save a PNG and exit — see scripts/screenshot_app.py.
        `self_test` checks that a (packaged) build works end to end and returns 0 or 1 — see `_self_test`."""

        _set_surface_format()
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName("PressToShape")
        app.setWindowIcon(icon(icons.APP))
        theme.apply(app)
        self._qt_translator = qt_translator(self.language.code)
        if self._qt_translator is not None:
            app.installTranslator(self._qt_translator)

        if self._settings is None:
            window = MainWindow(self.session)
            window.resize(*window_placement.DEFAULT_SIZE)
            window.show()
        else:
            window = MainWindow(self.session, self._settings)
            window_placement.show(window, self._settings)

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
        # After the window got its size: the New Document dialog opens over it.
        QTimer.singleShot(0, window.start)
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
    """Exercises what a broken bundle would miss: assets, translations, Skia rendering, path ops and SVG round
    trips."""
    german = languages.load_catalog(languages.Language("de", shipped=languages.SHIPPED_FOLDER / "de.po"))
    if german.gettext(None, "&File") != "&Datei":
        raise RuntimeError(f"German translation missing in {languages.SHIPPED_FOLDER}")
    if qt_translator("de") is None:
        raise RuntimeError("Qt's German translation (qtbase_de.qm) is missing")
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
        png_path = Path(folder) / "test.png"
        for name in ("test.svg", "test.p2s"):
            path = str(Path(folder) / name)
            if not documents.save_file(session, path):
                raise RuntimeError(f"saving {name} failed: {session.state.status_message}")
            if not documents.open_file(session, path):
                raise RuntimeError(f"opening {name} failed: {session.state.status_message}")
            reopened = queries.pickable_shapes(session.state)
            if len(reopened) != count or not any(isinstance(shape, CompositeShape) for shape in reopened):
                raise RuntimeError(f"{name} round trip lost shapes or the composite")
        if not documents.export_png(session, str(png_path), 1.0) or png_path.stat().st_size == 0:
            raise RuntimeError(f"PNG export failed: {session.state.status_message}")

    window.canvas.center_artboard()
    app.processEvents()
    image = window.grab().toImage()
    sampled = {image.pixel(x, y) for x in range(0, image.width(), 7) for y in range(0, image.height(), 7)}
    if len(sampled) < 8:
        raise RuntimeError(f"window looks blank ({len(sampled)} colors)")
