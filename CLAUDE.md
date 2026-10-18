# PressToShape — agent rules

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
- **skia-python** — renders the canvas and PNG export (`presstoshape/render/`). GPU through OpenGL inside a `QOpenGLWidget`, CPU raster fallback. No Metal backend, so macOS uses OpenGL 4.1 core.
- **skia-pathops** — boolean path ops in `presstoshape/geometry/booleans.py`: `combine_parts` (ordered parts with add/subtract/intersect/exclude modes; also computes Composite results), `divide`, `split_regions`. Works in float32; `_from_skia` rounds results.
- **svgelements** — only for parsing path `d` data, colors, lengths and transform strings in `formats/svg.py`. Don't use its `SVG.parse` document reader: it silently drops `display:none` groups (hidden layers) and `<text>`.

## Qt specifics

- **Icons: SVG, rendered as vectors.** Tabler outline SVGs live in `presstoshape/assets/icons/*.svg`, copied by `scripts/generate_icons.py` from `pytablericons` (dev-only dep — the running app never imports it). Regenerate with `uv run --group dev python scripts/generate_icons.py` after editing the mapping in that script. Reference paths via `presstoshape/icons.py`, load with `presstoshape.views.icon_engine.icon(path)` — its `SvgIconEngine` recolors `currentColor` per icon mode/state (normal / checked / disabled, colors in `views/theme.py`) and renders at the exact size × devicePixelRatio. Don't use `QIcon(path)` directly: Qt's SVG icon engine leaves `currentColor` black.
- Connect `QAction.triggered` / `clicked` through `lambda: slot()` — those signals pass a `checked` bool that would otherwise land in a slot's first optional parameter (e.g. a slot with `path=None` → `path=False`).
- Lifetime: Qt may delete C++ objects before their Python wrappers. Give widgets a parent, and disconnect signals that fire during teardown.
- Don't rebuild a widget (e.g. `QListWidget.clear()`) from inside one of its own item signals; defer with `QTimer.singleShot(0, ...)` (see `LayersPanel._on_item_changed`).
- Paint defaults must match SVG so canvas, export and saved file look the same: nonzero (winding) fill, butt cap, miter join, miter limit 4 (`render/paths.py`).

## Skia specifics

- The canvas viewport is a Skia surface widget (`views/skia_surface.py`): `SkiaGLWidget` or `SkiaRasterWidget`. The raster one is used on the `offscreen` platform, with `PRESSTOSHAPE_RENDERER=cpu`, or when GL init fails. `PRESSTOSHAPE_RENDERER=gl` forces GPU.
- GL lifetime: Skia's `GrDirectContext` must be released before the GL context dies → `CanvasView.shutdown()` calls `release()` while the widget lives. `aboutToBeDestroyed` also fires from the widget's C++ destructor (the Python `self` is already gone), so that handler only abandons the Skia context and makes no GL calls.
- `QOpenGLWidget.repaint()` doesn't run `paintGL` synchronously; benchmarks call `paintGL()` with the context current (`scripts/bench_canvas.py`).
- `QAbstractScrollArea` filters its viewport's events; `CanvasView.viewportEvent` lets Paint/Resize through so the surface widget paints and resizes its framebuffer.
- Keep viewport scroll whole-pixel (`Viewport.clamped`): half-pixel offsets blur hairlines and skew drag deltas.
- Per-frame cost is mostly Python→Skia call overhead: the canvas replays recorded pictures (`render/picture.py`) instead of drawing shapes one by one, and rects/ovals/text use `drawRect`/`drawOval`/`drawTextBlob` (fast GPU paths) rather than generic paths. Text outlines for hit-testing/bounds come from the same font setup (`render/text.py`).

## Architecture: session, operations, tools, views

Structured like professional editors (Blender, Krita, Inkscape): one state, edits as named operations, tools that turn input into operations, views that re-render from state. Qt is retained-mode, but state ownership stays Elm-like.

```
main.py                       # thin: sys.exit(App().run())
presstoshape/
├── app.py                    # creates the Session + MainWindow, owns QApplication; --self-test smoke check
├── version.py                # app version (build stamp or pyproject.toml)
├── icons.py                  # semantic icon path constants (views only)
├── models/                   # plain data: app_state.py (AppState, Document, Layer, Tool), shapes.py (frozen)
├── geometry/                 # pure shape math, no state
│   ├── affine.py             # 2D affine tuples (SVG matrix order)
│   ├── boxes.py              # Point, Rect, drag boxes
│   ├── segments.py           # building/mapping path segments
│   ├── booleans.py           # ordered-parts booleans, divide, regions (skia-pathops)
│   ├── transforms.py         # outline, translate, canonical shape transforms
│   └── nodes.py              # path node editing
├── formats/svg.py            # SVG read/write
├── render/                   # Skia drawing: model -> skia.Canvas
│   ├── scene.py / picture.py # document, overlays; recorded-picture replay
│   ├── paths.py / text.py    # cached shape paths, text outlines
│   ├── hit_test.py / handles.py   # picking: shapes, selection frame, handles, nodes
│   ├── viewport.py           # doc <-> screen mapping, zoom anchoring, scroll model
│   └── export.py             # PNG export
├── editing/
│   ├── session.py            # Session: the AppState, labelled undo history, subscribe/notify, edit()
│   ├── registry.py           # registered operations: id, menu label, can_run
│   ├── queries.py            # read-only questions about state
│   ├── containers.py         # active container (layer or entered Composite): pickable shapes, change_container
│   └── operations/           # the only code that changes state, one module per feature
├── tools/                    # Qt-free input state machines
│   ├── base.py               # Mods, CursorType, ToolContext, BaseTool
│   ├── registry.py           # TOOLS (display order) + Toolbox
│   └── select.py / node.py / pen.py / shapes.py / text.py
└── views/                    # Qt widgets only
    ├── main_window.py        # assembles panels, refresh() fans out, window commands (dialogs)
    ├── keymap.py             # shortcuts, icons, menu/toolbar layouts per command id
    ├── actions.py            # QActions built from the operation/tool registries + keymap
    ├── canvas_view.py        # scroll area + Skia surface: zoom/pan, forwards input to the active tool
    ├── cursors.py            # CursorType -> QCursor
    ├── skia_surface.py       # GL / raster Skia surface widgets
    └── *_view.py / widgets.py / theme.py / icon_engine.py / export_dialog.py
```

Rules:
- Import direction: `models <- geometry <- render <- editing <- tools <- views`; `formats` uses only models + geometry; `editing` may use formats and render (export, text outlines). `tests/test_architecture.py` enforces it.
- **No Qt below `views/`** (models, geometry, formats, render, editing, tools). That keeps them unit-testable without a display. `render/` can't see `views/theme.py`; views pass colors in (`CanvasColors`).
- Import with the `presstoshape.` prefix everywhere (`from presstoshape.models.app_state import AppState`).
- Data flow: input → tool or view → operation function → `session.edit(label)` records undo and mutates `AppState` → `session.notify()` → `MainWindow.refresh()` → every view's `refresh(state)`. Views and tools never assign to `AppState`.
- Operations are plain functions `operation(session, ...)` in `editing/operations/<feature>.py`. Document edits go inside `with session.edit("Label"):` (one undo step, named in the Undo menu; `merge_key` merges spinbox steps). Non-document changes (selection, tool, zoom) mutate and call `session.notify()`. Notify even on rejected input when a view needs to revert (e.g. `rename_layer`). Operations take plain values; dialogs stay in views.
- Commands without extra input (menus, shortcuts) are registered with `@operation("edit.delete", "&Delete", can_run=...)`; shortcuts and icons go in `views/keymap.py`, not next to the operation. Window commands needing dialogs are `WINDOW_COMMANDS` in the keymap, implemented by `MainWindow`.
- Tools subclass `BaseTool` and are listed in `tools/registry.py`; they keep gesture state (drag start, pen points, previews) until they commit through one operation call. `CanvasView` never checks tool types.
- View `refresh(state)` must be idempotent and cheap; block widget signals while writing values back (`blockSignals(True)`), and skip expensive rebuilds when the relevant slice of state is unchanged.
- The canvas redraws everything from state each frame. `PathCache` keys Skia geometry by shape id and rebuilds when the frozen shape changes. While a gesture runs, the tool reports the moving ids plus a doc-space `matrix` (move/rotate) or exact `live` replacement shapes (scale, node drags) in its `Overlay`, so the recorded picture is reused.
- Composites: `AppState.edit_path` holds the ids of the entered Composites (outer to inner). Operations reach "the shapes being edited" only through `editing/containers.py` (`pickable_shapes`, `change_container`), never `layer.shapes` directly, so they work the same on layer shapes and on parts. Part modes stay keyed by part id when lists are rebuilt. Enter/leave are not undo steps; `Session` trims a stale `edit_path` after undo.
- Shapes are frozen; change them with `dataclasses.replace`. Undo snapshots copy layer lists only and share shape objects.
- Shape `transform` stays canonical: go through `geometry.transforms` (`transform_shape`, `translate`, `with_rotation`) rather than composing matrices onto shapes by hand. Paths keep an identity transform (baked into segments).
- Tools decide cursors as `CursorType` (Qt-free, tested); only `views/cursors.py` maps them to Qt.
- One `Session` per app, created by `App` and passed explicitly — no module-level state. The registries hold definitions only. Nest sub-dataclasses per feature in `models/` rather than separate singletons.

## Code style

- Default: no comments. Only add one for a non-obvious *why*.
- Don't wrap Qt calls in defensive try/except; only guard real I/O/external boundaries (file load/save, parsing foreign SVG).
- Keep views small and composable (one class/module per panel), state passed in explicitly.

## Packaging and nightlies

- `.github/workflows/nightly.yml` only orchestrates; all packaging logic is in `scripts/build_package.py` (subcommands `version`, `linux`, `windows`, `test-msi`, `source`, `notes`), which runs the same locally: `uv run --group build python scripts/build_package.py linux`. Build tools live in the `build` dependency group; outputs go to `dist/` and `build/` (gitignored).
- Static inputs are in `packaging/` (PyInstaller spec, WiX source, desktop entry, AppImage excludelist, release-notes template, license texts that wheels don't ship). Every bundled component needs its license in `license_sources()`; the build fails on a missing one.
- PyInstaller runs in onedir mode (Qt as separate libraries for the LGPL). Assets are found through `Path(__file__)`, which works frozen; keep it that way.
- `presstoshape/version.py` reads the generated, gitignored `presstoshape/_build_info.py` in builds, `pyproject.toml` from source. `main.py --self-test` is the headless smoke check every build must pass; extend it when adding something a frozen bundle could miss (new data files, plugins, native libraries).
- Pin everything: actions by commit SHA, WiX by version (its v7 EULA is accepted with `-acceptEula wix7`; free under the OSMF revenue threshold), downloaded tools by SHA-256 in `build_package.py`.
- Trial runs never publish to `nightly`: only `main` defaults to that tag, other refs to `nightly-test`.

## Testing

- Everything below `views/` is tested with `pytest`: `uv run pytest`. Tests mirror the package layout (`tests/editing/test_layers.py`, `tests/tools/test_select.py`, …); shared helpers live in `tests/helpers.py` (`ToolDriver`, `all_shapes`), the `session` fixture in `tests/conftest.py`. New logic goes there with tests. Pixel assertions are fine on `render/` CPU-surface output.
- **Visual checks**: `uv run python scripts/screenshot_app.py` renders the window offscreen (`QT_QPA_PLATFORM=offscreen`) with demo shapes (`--empty` for none) and saves `dev-screenshots/app.png` (gitignored). Read the PNG; crop/zoom small regions with Pillow (dev dep via pytablericons) before reading when checking fine detail. Delete scratch crops after use.
- For interaction checks, drive the real window headless with `PySide6.QtTest.QTest` (mouse press/move/release on `canvas.viewport()`, doc → screen via `canvas._vp.to_screen`) in a scratch script; run once offscreen (raster) and once on the desktop (GL). Don't add whole-window pixel assertions to the pytest suite.
- Canvas performance: `uv run python scripts/bench_canvas.py` (10k shapes; `PRESSTOSHAPE_RENDERER=cpu` for the raster path).
