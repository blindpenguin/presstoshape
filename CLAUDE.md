# veccy — agent rules

Python SVG editor built on [PySide6](https://doc.qt.io/qtforpython-6/) (Qt 6 Widgets + QGraphicsView). Managed with `uv`.

## Project management (uv)

- Use `uv` for everything — never bare `pip`/`python -m venv`.
  - Add dep: `uv add <pkg>`
  - Add dev dep: `uv add --dev <pkg>` (pytest, ruff, mypy, etc.)
  - Run app/scripts: `uv run python main.py` (never activate venv manually)
  - Sync env after pulling changes: `uv sync`
  - Lockfile `uv.lock` is committed; never hand-edit it.
- Pin `requires-python` in `pyproject.toml` to a concrete floor — PySide6 wheels trail new CPython releases, so don't assume latest Python works.
- Keep `pyside6-essentials` pinned (`==`) — Qt behavior and PySide binding details shift between minors. Use `pyside6-essentials`, not the `pyside6` metapackage (that pulls in WebEngine/addons, hundreds of MB, unused). QtCore/QtGui/QtWidgets/QtSvg/QtSvgWidgets/QtTest are all in essentials.

## Libraries

- **PySide6** — UI and canvas rendering. Import from `PySide6.QtWidgets` etc.; never mix with PyQt5/6 (different bindings, incompatible objects).
- **skia-pathops** — boolean path ops (union/difference). Used from `veccy/controllers/geometry.py`, so controllers stay Qt-free. Works in float32; `_from_skia` rounds results.
- **svgelements** — only for parsing path `d` data, colors, lengths and transform strings in `svg_io.py`. Don't use its `SVG.parse` document reader: it silently drops `display:none` groups (hidden layers) and `<text>`.

## Qt specifics

- **Icons: SVG, rendered as vectors.** Tabler outline SVGs live in `veccy/assets/icons/*.svg`, copied by `scripts/generate_icons.py` from `pytablericons` (dev-only dep — the running app never imports it). Regenerate with `uv run --group dev python scripts/generate_icons.py` after editing the mapping in that script. Reference paths via `veccy/icons.py`, load with `veccy.views.icon_engine.icon(path)` — its `SvgIconEngine` recolors `currentColor` per icon mode/state (normal / checked / disabled, colors in `views/theme.py`) and renders at the exact size × devicePixelRatio. Don't use `QIcon(path)` directly: Qt's SVG icon engine leaves `currentColor` black.
- Connect `QAction.triggered` / `clicked` through `lambda: slot()` — those signals pass a `checked` bool that would otherwise land in a slot's first optional parameter (e.g. `save_file(path=None)` → `path=False`).
- Lifetime: Qt may delete C++ objects before their Python wrappers. Give widgets/scenes a parent, and disconnect signals that fire during teardown (see `CanvasView.shutdown()` — scene destruction emits `selectionChanged`).
- Don't rebuild a widget (e.g. `QListWidget.clear()`) from inside one of its own item signals; defer with `QTimer.singleShot(0, ...)` (see `LayersPanel._on_item_changed`).
- `QPainterPath` defaults to odd-even fill; SVG's default is nonzero → always `setFillRule(Qt.FillRule.WindingFill)` when converting model paths.
- Pen defaults must match SVG (flat cap, miter join) so canvas and saved file look the same.

## Architecture: Model / View / Controller

Qt is retained-mode, but state ownership stays Elm-like: the model is the single source of truth, views are re-rendered from it, controllers are the only writers.

```
main.py                       # thin: sys.exit(App().run())
veccy/
├── app.py                    # creates AppState + AppController + MainWindow, owns QApplication
├── icons.py                  # semantic icon path constants
├── models/
│   ├── app_state.py          # AppState, Document, Layer, Tool — plain dataclasses
│   └── shapes.py             # frozen shape + path-segment dataclasses
├── controllers/
│   ├── app_controller.py     # all state mutation, undo/redo, file I/O, subscribe/notify
│   ├── geometry.py           # pure geometry + booleans (skia-pathops)
│   └── svg_io.py             # SVG read/write
└── views/
    ├── main_window.py        # assembles panels, refresh() fans out, dialogs
    ├── actions.py            # every QAction (shared by menus + toolbars)
    ├── canvas_view.py        # QGraphicsView: syncs scene from model, gestures -> controller
    └── *_view.py / widgets.py / theme.py / icon_engine.py
```

Rules:
- Dependency direction: `veccy.views -> veccy.controllers -> veccy.models`. Never import a view from a model or controller.
- **No Qt imports in `models/` or `controllers/`.** That's what keeps them unit-testable without a display.
- Import with the `veccy.` prefix everywhere (`from veccy.models.app_state import AppState`).
- Data flow: user input → view calls a controller method → controller mutates `AppState`, then `_notify()` → `MainWindow.refresh()` → every view's `refresh(state)` re-renders. Views never mutate state directly.
- Every controller method that changes state must call `self._notify()` (even on rejected input when a view needs to revert, e.g. `rename_layer`). Document mutations call `self._checkpoint()` *before* mutating to record undo.
- View `refresh(state)` must be idempotent and cheap; block widget signals while writing values back (`blockSignals(True)`), and skip expensive rebuilds when the relevant slice of state is unchanged.
- Transient gesture state (drag start, pen points in progress, preview item, pan) lives in the view; it's not app state until the gesture commits to a controller call.
- `CanvasView` keeps scene items as a cache keyed by shape id, diffed by frozen-dataclass equality. Qt moves items live while dragging; on release the offset goes to `controller.move_selection` and the next sync snaps items back to `pos (0, 0)` — shape geometry is always in absolute document coordinates.
- Shapes are frozen; change them with `dataclasses.replace`. Undo snapshots copy layer lists only and share shape objects.
- One `AppState` per app, passed explicitly through `App` — no module-level globals for state. Nest sub-dataclasses per feature in `models/` rather than separate singletons.
- Dialogs (file pickers, confirmations, text input) live in views; controllers receive plain values (paths, strings).

## Code style

- Default: no comments. Only add one for a non-obvious *why*.
- Don't wrap Qt calls in defensive try/except; only guard real I/O/external boundaries (file load/save, parsing foreign SVG).
- Keep views small and composable (one class/module per panel), state passed in explicitly.

## Testing

- Models/controllers/geometry/svg_io are tested with `pytest`: `uv run pytest`. New logic goes there with tests.
- **Visual checks**: `uv run python scripts/screenshot_app.py` renders the window offscreen (`QT_QPA_PLATFORM=offscreen`) with demo shapes (`--empty` for none) and saves `dev-screenshots/app.png` (gitignored). Read the PNG; crop/zoom small regions with Pillow (dev dep via pytablericons) before reading when checking fine detail. Delete scratch crops after use.
- For interaction checks, drive the real window headless with `PySide6.QtTest.QTest` (mouse press/move/release on `canvas.viewport()`, `mapFromScene` for coordinates) in a scratch script. Don't add pixel assertions to the pytest suite.
