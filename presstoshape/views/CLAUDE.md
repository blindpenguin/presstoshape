# views/ — Qt widgets

```
views/
├── main_window.py        # assembles panels, refresh() fans out, window commands (dialogs)
├── keymap.py             # shortcuts, icons, menu/toolbar layouts per command id
├── actions.py            # QActions built from the operation/tool registries + keymap
├── canvas_view.py        # scroll area + Skia surface: zoom/pan, forwards input to the active tool
├── settings/             # Settings window: dialog + one page per category (PAGES in dialog.py)
├── cursors.py            # CursorType -> QCursor
├── skia_surface.py       # GL / raster Skia surface widgets
└── *_view.py / widgets.py / theme.py / icon_engine.py / export_dialog.py / corner_dialog.py
```

## Rules

- View `refresh(state)` must be idempotent and cheap; block widget signals while writing values back (`blockSignals(True)`), and skip expensive rebuilds when the relevant slice of state is unchanged.
- Shortcuts and icons go in `views/keymap.py`, not next to the operation. Window commands needing dialogs are `WINDOW_COMMANDS` in the keymap, implemented by `MainWindow`.
- Shortcuts only for frequent actions during drawing and editing (tools, clipboard, undo, booleans, zoom, file basics). Rarely used commands and windows (Settings, About, rare dialogs) get a menu entry, no shortcut: every binding uses up a key combination and can clash with the system or later features. Don't add one just because a command exists; ask when unsure.
- `CanvasView` never checks tool types.
- Tests and scripts that build a `MainWindow` with settings pass their own `recovery_folder` and `palettes_folder`.

## Qt specifics

- **Icons: SVG, rendered as vectors.** Tabler outline SVGs live in `presstoshape/assets/icons/*.svg`, copied by `scripts/generate_icons.py` from `pytablericons` (dev-only dep — the running app never imports it). Regenerate with `uv run --group dev python scripts/generate_icons.py` after editing the mapping in that script. Reference paths via `presstoshape/icons.py`, load with `presstoshape.views.icon_engine.icon(path)` — its `SvgIconEngine` recolors `currentColor` per icon mode/state (normal / checked / disabled, colors in `views/theme.py`) and renders at the exact size × devicePixelRatio. Don't use `QIcon(path)` directly: Qt's SVG icon engine leaves `currentColor` black.
- Connect `QAction.triggered` / `clicked` through `lambda: slot()` — those signals pass a `checked` bool that would otherwise land in a slot's first optional parameter (e.g. a slot with `path=None` → `path=False`).
- Lifetime: Qt may delete C++ objects before their Python wrappers. Give widgets a parent, and disconnect signals that fire during teardown.
- Don't rebuild a widget (e.g. `QListWidget.clear()`) from inside one of its own item signals; defer with `QTimer.singleShot(0, ...)` (see `LayersPanel._on_item_changed`).

## Skia surface and GL

- The canvas viewport is a Skia surface widget (`views/skia_surface.py`): `SkiaGLWidget` or `SkiaRasterWidget`. The raster one is used on the `offscreen` platform, with `PRESSTOSHAPE_RENDERER=cpu`, or when GL init fails. `PRESSTOSHAPE_RENDERER=gl` forces GPU.
- GL init: `GrDirectContext.MakeGL()` loads GL through GLX only; Qt on Wayland runs on EGL, so `SkiaGLWidget` falls back to `MakeGL(GrGLInterface.MakeEGL())` before giving up on the GPU.
- GL lifetime: Skia's `GrDirectContext` must be released before the GL context dies → `CanvasView.shutdown()` calls `release()` while the widget lives. `aboutToBeDestroyed` also fires from the widget's C++ destructor (the Python `self` is already gone), so that handler only abandons the Skia context and makes no GL calls.
- `QOpenGLWidget.repaint()` doesn't run `paintGL` synchronously; benchmarks call `paintGL()` with the context current (`scripts/bench_canvas.py`).
- `QAbstractScrollArea` filters its viewport's events; `CanvasView.viewportEvent` lets Paint/Resize through so the surface widget paints and resizes its framebuffer.
- Keep viewport scroll whole-pixel (`Viewport.clamped`): half-pixel offsets blur hairlines and skew drag deltas.

## Checking the real window

- **Visual checks**: `uv run python scripts/screenshot_app.py` renders the window offscreen (`QT_QPA_PLATFORM=offscreen`) with demo shapes (`--empty` for none) and saves `dev-screenshots/app.png` (gitignored). Read the PNG; crop/zoom small regions with Pillow (dev dep via pytablericons) before reading when checking fine detail. Delete scratch crops after use.
- For interaction checks, drive the real window headless with `PySide6.QtTest.QTest` (mouse press/move/release on `canvas.viewport()`, doc → screen via `canvas._vp.to_screen`) in a scratch script; run once offscreen (raster) and once on the desktop (GL). Don't add whole-window pixel assertions to the pytest suite.
