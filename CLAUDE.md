# veccy — agent rules

Python SVG editor built on [PySide6](https://doc.qt.io/qtforpython-6/) (Qt 6 Widgets) with a Skia-rendered canvas. Managed with `uv`.

## Project management (uv)

- Use `uv` for everything — never bare `pip`/`python -m venv`.
  - Add dep: `uv add <pkg>`
  - Add dev dep: `uv add --dev <pkg>` (pytest, ruff, mypy, etc.)
  - Run app/scripts: `uv run python main.py` (never activate venv manually)
  - Sync env after pulling changes: `uv sync`
  - Lockfile `uv.lock` is committed; never hand-edit it.
- Pin `requires-python` in `pyproject.toml` to a concrete floor — PySide6 wheels trail new CPython releases, so don't assume latest Python works.
- Keep `pyside6-essentials` pinned (`==`) — Qt behavior and PySide binding details shift between minors. Use `pyside6-essentials`, not the `pyside6` metapackage (that pulls in WebEngine/addons, hundreds of MB, unused). QtCore/QtGui/QtWidgets/QtSvg/QtSvgWidgets/QtTest are all in essentials.

## Feature workflow (spec-workflow MCP)

- The `spec-workflow` MCP server (`.mcp.json`, pinned to `@pimzino/spec-workflow-mcp@2.2.5`) drives non-trivial features: Requirements → Design → Tasks, each approved by the user in its dashboard before moving on, then implementation task by task with logs. Specs and steering docs live in `.spec-workflow/` and are committed.
- Use it for new features or cross-cutting changes. Small fixes (single bug, tweak, rename) skip it.
- Dashboard: `scripts/spec_dashboard.sh` (reads the pinned version from `.mcp.json`; `--port N`, `--no-open`) → http://localhost:5000. The user runs it; don't start long-running servers yourself.
- Bump the pinned version deliberately (check the changelog), never switch to `@latest` — npx would run unreviewed new code on every launch.

## Libraries

- **PySide6** — UI, input and the canvas GL context. Import from `PySide6.QtWidgets` etc.; never mix with PyQt5/6 (different bindings, incompatible objects).
- **skia-python** — renders the canvas and PNG export (`veccy/render/`). GPU through OpenGL inside a `QOpenGLWidget`, CPU raster fallback. No Metal backend, so macOS uses OpenGL 4.1 core.
- **skia-pathops** — boolean path ops (union/difference). Used from `veccy/controllers/geometry.py`, so controllers stay Qt-free. Works in float32; `_from_skia` rounds results.
- **svgelements** — only for parsing path `d` data, colors, lengths and transform strings in `svg_io.py`. Don't use its `SVG.parse` document reader: it silently drops `display:none` groups (hidden layers) and `<text>`.

## Qt specifics

- **Icons: SVG, rendered as vectors.** Tabler outline SVGs live in `veccy/assets/icons/*.svg`, copied by `scripts/generate_icons.py` from `pytablericons` (dev-only dep — the running app never imports it). Regenerate with `uv run --group dev python scripts/generate_icons.py` after editing the mapping in that script. Reference paths via `veccy/icons.py`, load with `veccy.views.icon_engine.icon(path)` — its `SvgIconEngine` recolors `currentColor` per icon mode/state (normal / checked / disabled, colors in `views/theme.py`) and renders at the exact size × devicePixelRatio. Don't use `QIcon(path)` directly: Qt's SVG icon engine leaves `currentColor` black.
- Connect `QAction.triggered` / `clicked` through `lambda: slot()` — those signals pass a `checked` bool that would otherwise land in a slot's first optional parameter (e.g. `save_file(path=None)` → `path=False`).
- Lifetime: Qt may delete C++ objects before their Python wrappers. Give widgets a parent, and disconnect signals that fire during teardown.
- Don't rebuild a widget (e.g. `QListWidget.clear()`) from inside one of its own item signals; defer with `QTimer.singleShot(0, ...)` (see `LayersPanel._on_item_changed`).
- Paint defaults must match SVG so canvas, export and saved file look the same: nonzero (winding) fill, butt cap, miter join, miter limit 4 (`render/paths.py`).

## Skia specifics

- The canvas viewport is a Skia surface widget (`views/skia_surface.py`): `SkiaGLWidget` or `SkiaRasterWidget`. The raster one is used on the `offscreen` platform, with `VECCY_RENDERER=cpu`, or when GL init fails. `VECCY_RENDERER=gl` forces GPU.
- GL lifetime: Skia's `GrDirectContext` must be released before the GL context dies → `CanvasView.shutdown()` calls `release()` while the widget lives. `aboutToBeDestroyed` also fires from the widget's C++ destructor (the Python `self` is already gone), so that handler only abandons the Skia context and makes no GL calls.
- `QOpenGLWidget.repaint()` doesn't run `paintGL` synchronously; benchmarks call `paintGL()` with the context current (`scripts/bench_canvas.py`).
- `QAbstractScrollArea` filters its viewport's events; `CanvasView.viewportEvent` lets Paint/Resize through so the surface widget paints and resizes its framebuffer.
- Keep viewport scroll whole-pixel (`Viewport.clamped`): half-pixel offsets blur hairlines and skew drag deltas.
- Per-frame cost is mostly Python→Skia call overhead: the canvas replays recorded pictures (`render/picture.py`) instead of drawing shapes one by one, and rects/ovals/text use `drawRect`/`drawOval`/`drawTextBlob` (fast GPU paths) rather than generic paths. Text outlines for hit-testing/bounds come from the same font setup (`render/text.py`).

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
│   ├── app_controller.py     # all state mutation, undo/redo, file I/O, export, subscribe/notify
│   ├── geometry.py           # pure geometry + booleans (skia-pathops)
│   └── svg_io.py             # SVG read/write
├── render/                   # Qt-free Skia drawing: model -> skia.Canvas
│   ├── scene.py              # document, background, overlays (selection, rubber band, preview)
│   ├── picture.py            # recorded-picture replay for the canvas
│   ├── paths.py / text.py    # cached shape paths, text outlines
│   ├── hit_test.py           # click + rubber-band picking
│   ├── viewport.py           # doc <-> screen mapping, zoom anchoring, scroll model
│   └── export.py             # PNG export
└── views/
    ├── main_window.py        # assembles panels, refresh() fans out, dialogs
    ├── actions.py            # every QAction (shared by menus + toolbars)
    ├── canvas_view.py        # scroll area + Skia surface: zoom/pan, paints from state
    ├── canvas_gestures.py    # per-tool gesture state (Qt-free) -> controller
    ├── skia_surface.py       # GL / raster Skia surface widgets
    └── *_view.py / widgets.py / theme.py / icon_engine.py / export_dialog.py
```

Rules:
- Dependency direction: `veccy.views -> veccy.controllers -> veccy.render -> veccy.models` (views also use `render` directly). Never import a view from a model, controller or renderer; `render` never mutates state.
- **No Qt imports in `models/`, `controllers/` or `render/`.** That's what keeps them unit-testable without a display. `render/` can't see `views/theme.py`; views pass colors in (`CanvasColors`).
- Import with the `veccy.` prefix everywhere (`from veccy.models.app_state import AppState`).
- Data flow: user input → view calls a controller method → controller mutates `AppState`, then `_notify()` → `MainWindow.refresh()` → every view's `refresh(state)` re-renders. Views never mutate state directly.
- Every controller method that changes state must call `self._notify()` (even on rejected input when a view needs to revert, e.g. `rename_layer`). Document mutations call `self._checkpoint()` *before* mutating to record undo.
- View `refresh(state)` must be idempotent and cheap; block widget signals while writing values back (`blockSignals(True)`), and skip expensive rebuilds when the relevant slice of state is unchanged.
- Transient gesture state (drag start, pen points in progress, preview item, pan) lives in the view; it's not app state until the gesture commits to a controller call.
- The canvas redraws everything from state each frame. `PathCache` keys Skia geometry by shape id and rebuilds when the frozen shape changes. While dragging, `CanvasGestures` reports the moving ids + offset in its `Overlay`; on release the offset goes to `controller.move_selection` — shape geometry is always in absolute document coordinates.
- Shapes are frozen; change them with `dataclasses.replace`. Undo snapshots copy layer lists only and share shape objects.
- One `AppState` per app, passed explicitly through `App` — no module-level globals for state. Nest sub-dataclasses per feature in `models/` rather than separate singletons.
- Dialogs (file pickers, confirmations, text input) live in views; controllers receive plain values (paths, strings).

## Code style

- Default: no comments. Only add one for a non-obvious *why*.
- Don't wrap Qt calls in defensive try/except; only guard real I/O/external boundaries (file load/save, parsing foreign SVG).
- Keep views small and composable (one class/module per panel), state passed in explicitly.

## Testing

- Models/controllers/geometry/svg_io/render and `canvas_gestures` are tested with `pytest`: `uv run pytest`. New logic goes there with tests. Pixel assertions are fine on `render/` CPU-surface output.
- **Visual checks**: `uv run python scripts/screenshot_app.py` renders the window offscreen (`QT_QPA_PLATFORM=offscreen`) with demo shapes (`--empty` for none) and saves `dev-screenshots/app.png` (gitignored). Read the PNG; crop/zoom small regions with Pillow (dev dep via pytablericons) before reading when checking fine detail. Delete scratch crops after use.
- For interaction checks, drive the real window headless with `PySide6.QtTest.QTest` (mouse press/move/release on `canvas.viewport()`, doc → screen via `canvas._vp.to_screen`) in a scratch script; run once offscreen (raster) and once on the desktop (GL). Don't add whole-window pixel assertions to the pytest suite.
- Canvas performance: `uv run python scripts/bench_canvas.py` (10k shapes; `VECCY_RENDERER=cpu` for the raster path).
