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

## Git workflow

- One-person project: commit directly to `main`, no pull requests and no merge commits. Don't create a branch just to commit.
- One commit per finished feature or fix, with a descriptive message. Run `uv run ruff check .`, `uv run ruff format .` and `uv run pytest` before committing; nothing else gates `main` (the nightly runs the tests again before packaging).
- A branch only for large multi-session work that would leave `main` half-done: keep it local, then fast-forward or squash it into `main`.

## Libraries

- **PySide6** — UI, input and the canvas GL context. Import from `PySide6.QtWidgets` etc.; never mix with PyQt5/6 (different bindings, incompatible objects).
- **skia-python** — renders the canvas and PNG export (`presstoshape/render/`). GPU through OpenGL inside a `QOpenGLWidget`, CPU raster fallback. No Metal backend, so macOS uses OpenGL 4.1 core.
- **skia-pathops** — boolean path ops in `presstoshape/geometry/booleans.py`: `combine_parts` (ordered parts with add/subtract/intersect/exclude modes; also computes Composite results), `divide`, `split_regions`. Works in float32; `_from_skia` rounds results. Booleans, divide and Composite parts take `transforms.area_outline` (even-odd shapes made nonzero-safe), never `outline`, which stays the drawn contour.
- **svgelements** — only for parsing path `d` data, colors, lengths and transform strings (`formats/svg_values.py`, colours in `formats/svg_reader.py`). Don't use its `SVG.parse` document reader: it silently drops `display:none` groups (hidden layers) and `<text>`.

## Qt specifics

- **Icons: SVG, rendered as vectors.** Tabler outline SVGs live in `presstoshape/assets/icons/*.svg`, copied by `scripts/generate_icons.py` from `pytablericons` (dev-only dep — the running app never imports it). Regenerate with `uv run --group dev python scripts/generate_icons.py` after editing the mapping in that script. Reference paths via `presstoshape/icons.py`, load with `presstoshape.views.icon_engine.icon(path)` — its `SvgIconEngine` recolors `currentColor` per icon mode/state (normal / checked / disabled, colors in `views/theme.py`) and renders at the exact size × devicePixelRatio. Don't use `QIcon(path)` directly: Qt's SVG icon engine leaves `currentColor` black.
- Connect `QAction.triggered` / `clicked` through `lambda: slot()` — those signals pass a `checked` bool that would otherwise land in a slot's first optional parameter (e.g. a slot with `path=None` → `path=False`).
- Lifetime: Qt may delete C++ objects before their Python wrappers. Give widgets a parent, and disconnect signals that fire during teardown.
- Don't rebuild a widget (e.g. `QListWidget.clear()`) from inside one of its own item signals; defer with `QTimer.singleShot(0, ...)` (see `LayersPanel._on_item_changed`).
- Paint defaults must match SVG so canvas, export and saved file look the same: nonzero (winding) fill, butt cap, miter join, miter limit 4, opacity 1 (defaults on `models/shapes.Style`, applied in `render/paths.py` / `render/scene.py`). Keep values in range through `models.shapes.sanitized`. Opacity layers (`saveLayerAlpha`) only for shapes with fill and stroke below full opacity; everything else must cost nothing extra per frame.

## Skia specifics

- The canvas viewport is a Skia surface widget (`views/skia_surface.py`): `SkiaGLWidget` or `SkiaRasterWidget`. The raster one is used on the `offscreen` platform, with `PRESSTOSHAPE_RENDERER=cpu`, or when GL init fails. `PRESSTOSHAPE_RENDERER=gl` forces GPU.
- GL init: `GrDirectContext.MakeGL()` loads GL through GLX only; Qt on Wayland runs on EGL, so `SkiaGLWidget` falls back to `MakeGL(GrGLInterface.MakeEGL())` before giving up on the GPU.
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
├── app.py                    # resolves + installs the language, creates the Session + MainWindow, owns QApplication; --self-test
├── i18n/                     # translations, Qt-free bottom layer: _ / ngettext / pgettext / N_, PO parser, plural formulas, catalogs
├── version.py                # app version (build stamp or pyproject.toml)
├── icons.py                  # semantic icon path constants (views only)
├── models/                   # plain data: app_state.py (AppState, Document, Layer, Tool), shapes.py (frozen)
├── geometry/                 # pure shape math, no state
│   ├── affine.py             # 2D affine tuples (SVG matrix order)
│   ├── boxes.py              # Point, Rect, drag boxes
│   ├── align.py / snapping.py / rulers.py   # align/distribute offsets, snap targets and queries, ruler ticks
│   ├── aspect.py         # preserveAspectRatio: align/meet/slice for the SVG viewport and pictures (`fitted_rect`, `visible_box`)
│   ├── segments.py           # building/mapping path segments
│   ├── pen_paths.py          # Pen nodes (point + optional handles) → line/cubic segments, open or closed
│   ├── booleans.py           # ordered-parts booleans, divide, regions (skia-pathops)
│   ├── transforms.py         # outline, translate, canonical shape transforms
│   ├── nodes.py              # path node editing
│   ├── path_edit.py          # path structure: node types, break/join, close/open, reverse, combine/split
│   ├── corners.py            # live corners: rounded outline (used by transforms.outline), corner widget math
│   └── fitting.py            # freehand strokes → cubic beziers (Pencil)
├── formats/                  # svg.py (SVG write + public read API), svg_reader.py (cascade, <use>, text lines), css.py (<style> subset),
│                             # svg_values.py / svg_names.py / svg_page.py / svg_notes.py (import notes for the report dialog), svg_nodetypes.py (corner nodes as `sodipodi:nodetypes`), svg_corners.py (live corners in path metadata),
│                             # image_info.py (picture header probe: type, size, limits, digest) + svg_images.py (`<image>` sources, never the network),
│                             # p2s.py + p2s_migrations.py (native .p2s, docs/file-format.md),
│                             # clipboard.py (shape payload for copy/paste, not migrated: falls back to SVG)
├── render/                   # Skia drawing: model -> skia.Canvas
│   ├── scene.py / picture.py # document, overlays; recorded-picture replay
│   ├── images.py             # picture decode cache (LRU, mip levels for huge ones) and drawing; `PathCache.images`
│   ├── paths.py / text.py    # cached shape paths, text outlines
│   ├── hit_test.py / handles.py   # picking: shapes, selection frame, handles, nodes
│   ├── viewport.py           # doc <-> screen mapping, zoom anchoring, scroll model
│   └── export.py             # PNG export
├── editing/
│   ├── session.py            # Session: the AppState, labelled undo history, subscribe/notify, edit()
│   ├── registry.py           # registered operations: id, menu label, can_run
│   ├── queries.py            # read-only questions about state
│   ├── containers.py         # active container (layer, entered group or Composite): pickable shapes, change_container
│   └── operations/           # the only code that changes state, one module per feature
├── tools/                    # Qt-free input state machines
│   ├── base.py               # Mods, CursorType, ToolContext, BaseTool
│   ├── registry.py           # TOOLS (display order) + Toolbox
│   └── select.py / node.py / pen.py / pencil.py / shapes.py / text.py / eyedropper.py
└── views/                    # Qt widgets only
    ├── main_window.py        # assembles panels, refresh() fans out, window commands (dialogs)
    ├── keymap.py             # shortcuts, icons, menu/toolbar layouts per command id
    ├── actions.py            # QActions built from the operation/tool registries + keymap
    ├── canvas_view.py        # scroll area + Skia surface: zoom/pan, forwards input to the active tool
    ├── settings/             # Settings window: dialog + one page per category (PAGES in dialog.py)
    ├── cursors.py            # CursorType -> QCursor
    ├── skia_surface.py       # GL / raster Skia surface widgets
    └── *_view.py / widgets.py / theme.py / icon_engine.py / export_dialog.py / corner_dialog.py
```

Rules:
- Import direction: `models <- geometry <- render <- editing <- tools <- views`; `formats` uses only models + geometry; `editing` may use formats and render (export, text outlines). `i18n` is below everything and importable from every layer. `tests/test_architecture.py` enforces it.
- **No Qt below `views/`** (models, geometry, formats, render, editing, tools). That keeps them unit-testable without a display. `render/` can't see `views/theme.py`; views pass colors in (`CanvasColors`).
- Import with the `presstoshape.` prefix everywhere (`from presstoshape.models.app_state import AppState`).
- Data flow: input → tool or view → operation function → `session.edit(label)` records undo and mutates `AppState` → `session.notify()` → `MainWindow.refresh()` → every view's `refresh(state)`. Views and tools never assign to `AppState`.
- Operations are plain functions `operation(session, ...)` in `editing/operations/<feature>.py`. Document edits go inside `with session.edit("Label"):` (one undo step, named in the Undo menu; `merge_key` merges spinbox steps). Non-document changes (selection, tool, zoom) mutate and call `session.notify()`. Notify even on rejected input when a view needs to revert (e.g. `rename_layer`). Operations take plain values; dialogs stay in views.
- Commands without extra input (menus, shortcuts) are registered with `@operation("edit.delete", "&Delete", can_run=...)`; shortcuts and icons go in `views/keymap.py`, not next to the operation. Window commands needing dialogs are `WINDOW_COMMANDS` in the keymap, implemented by `MainWindow`.
- Shortcuts only for frequent actions during drawing and editing (tools, clipboard, undo, booleans, zoom, file basics). Rarely used commands and windows (Settings, About, rare dialogs) get a menu entry, no shortcut: every binding uses up a key combination and can clash with the system or later features. Don't add one just because a command exists; ask when unsure.
- Tools subclass `BaseTool` and are listed in `tools/registry.py`; they keep gesture state (drag start, pen points, previews) until they commit through one operation call. `CanvasView` never checks tool types.
- View `refresh(state)` must be idempotent and cheap; block widget signals while writing values back (`blockSignals(True)`), and skip expensive rebuilds when the relevant slice of state is unchanged.
- The canvas redraws everything from state each frame. `PathCache` keys Skia geometry by shape id and rebuilds when the frozen shape changes. While a gesture runs, the tool reports the moving ids plus a doc-space `matrix` (move/rotate) or exact `live` replacement shapes (scale, node drags) in its `Overlay`, so the recorded picture is reused.
- Native format `.p2s` (ZIP + JSON, `formats/p2s.py`): encoders/decoders are explicit per type, never generic over dataclass fields. Any change to what files store bumps `CURRENT_VERSION` in `formats/p2s_migrations.py`, adds a migration from the previous version, a `tests/formats/samples/v<N>.p2s` sample, and a row in `docs/file-format.md`. Everything the app can save must open again (tested round trips). Saves are atomic (`documents.write_atomically`) and can keep one backup of the previous file (`name.backup.ext`).
- Crash recovery (`editing/operations/recovery.py`, `views/recovery_keeper.py`): one rule, while the document is dirty its snapshot is at most one interval old, otherwise there is none. Snapshots live only in the app's recovery folder, never in user folders. Anything that replaces or saves the document just has to clear `dirty` (and bump `Session.revision` through `edit()`/`replace_document`); the keeper does the rest. Tests and scripts that build a `MainWindow` with settings pass their own `recovery_folder` and `library_path`.
- Groups and Composites are containers (`children_of`): `AppState.edit_path` holds the ids of the entered ones (outer to inner). Operations reach "the shapes being edited" only through `editing/containers.py` (`pickable_shapes`, `change_container`), never `layer.shapes` directly, so they work the same on layer shapes, group children and parts; rules that only hold for Composite parts (outlines, part modes, no text) check `edited_composite`. Part modes stay keyed by part id when lists are rebuilt; an entered container left empty is removed. Enter/leave (`operations/edit_mode.py`) are not undo steps; `Session` trims a stale `edit_path` after undo.
- `ImageShape` is a leaf with a shared `ImageData` blob (original file bytes, equality by digest; decoded lazily in `render/images.py`). It has no `style` either (only `opacity`), so code that reads `shape.style` handles images too; booleans, Composites and clip objects refuse them. Reference images (`reference=True`) are dimmed, locked, left out of exports and saved SVG; `PathCache.drawing(zoom, references)` carries the zoom and the show-references switch into recorded pictures. `.p2s` keeps the bytes as `media/<digest>.<ext>`, written once per distinct blob.
- `GroupShape` has no `style` and an identity transform: code that reads `shape.style` or recurses into shapes handles groups first (drawing, hit-testing, bounds, styling through `style.restyle_shape`, encoders).
- Shapes are frozen; change them with `dataclasses.replace`. Undo snapshots copy layer lists only and share shape objects.
- Coordinates are document pixels (1/`Document.dpi` inch) everywhere below the views. `Document.unit` only changes how lengths are shown and entered: convert at the widget boundary (`views/unit_fields.LengthSpinBox`, `geometry/units`), never in operations, geometry or rendering.
- Shape `transform` stays canonical: go through `geometry.transforms` (`transform_shape`, `translate`, `with_rotation`) rather than composing matrices onto shapes by hand. Paths keep an identity transform (baked into segments).
- A path's segments are its nodes; what is drawn is `transforms.outline` (it rounds live corners, `geometry/corners.py`). Code that draws, measures or combines a path goes through `outline` / `area_outline`, never `path.segments` directly; node editing works on the segments. Per-node data (`corner`, `rounding`) lives on the segment that ends at the node and survives edits through `dataclasses.replace`.
- Tools decide cursors as `CursorType` (Qt-free, tested); only `views/cursors.py` maps them to Qt.
- Snapping: tools build a `Snapper` once per gesture (`ToolContext.snapper(...)`, targets from the visible area) and ask it for corrected points/offsets while dragging; Ctrl ignores it; its hits go into `Overlay.snap` for feedback. The math lives in `geometry/snapping.py`, never per frame over all shapes.
- Colours (`editing/operations/colours.py`, `swatches.py`): every colour source (Colour panel, swatches, eyedropper, menu) goes through `apply_colour`, which writes the active paint of `queries.colour_target` (selection, else the active drawing tool's style, else `AppState.colours.current`). Document swatches are undoable and saved; recent colours and the library are app-level state that `MainWindow` persists (settings, `swatches.json` in the data folder). Picker drags with a selection preview through `CanvasView.set_style_preview` (Overlay `live`) and commit once on release: a document edit per mouse move re-records the whole picture.
- Guides and the grid belong to the `Document` (undoable, saved); show/lock/snap toggles are view state on `AppState` (rulers and snapping remembered in app settings, grid/guides visibility in `.p2s` working state). Commands with a check mark register a `checked` callback.
- One `Session` per app, created by `App` and passed explicitly — no module-level state. The registries hold definitions only. Nest sub-dataclasses per feature in `models/` rather than separate singletons. The one exception is the active translation catalog in `i18n`: installed once by `App` before the Session exists, read-only afterwards (a language change needs a restart).

## Translations (i18n)

- UI source texts are British English (centre, colour, …); English runs with the `en_GB` locale. Every user-visible text goes through `presstoshape.i18n`: `_("…")`, `ngettext("{count} object", "{count} objects", n).format(count=n)`, `pgettext("context", "…")` for ambiguous short words, `N_("…")` where a text is defined but shown elsewhere (registries, label tables), translated there with `_(label)`. Literals only; never f-strings or `.format()` inside the call. Not translated: log messages, ids, file keys, shortcuts.
- After changing UI text run `uv run python scripts/update_translations.py` (template `presstoshape/assets/translations/presstoshape.pot` + merge into shipped `.po`); then translate the new entries in `de.po`. Tests fail while the template is stale or `de.po` is incomplete, and when menu mnemonics clash.
- Don't name a variable `_` in a function that translates (`path, _chosen = QFileDialog...`).
- User translation files and how translators work: `docs/translating.md`.

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
- The portable ZIP (only) contains `portable.txt` next to the exe; `views/app_settings.py` then stores settings in `settings.ini` there instead of the registry. `test-msi` checks the installed app doesn't have it.
- Trial runs never publish to `nightly`: only `main` defaults to that tag, other refs to `nightly-test`.

## Testing

- Lint and format with ruff (config in `pyproject.toml`: line length 120, rules `E`/`F`/`I`, `.spec-workflow/` excluded): `uv run ruff check .` and `uv run ruff format .`. Run both before finishing a change; the formatter owns line wrapping, so don't hand-wrap.
- Everything below `views/` is tested with `pytest`: `uv run pytest`. Tests mirror the package layout (`tests/editing/test_layers.py`, `tests/tools/test_select.py`, …); shared helpers live in `tests/helpers.py` (`ToolDriver`, `all_shapes`), the `session` fixture in `tests/conftest.py`. New logic goes there with tests. Pixel assertions are fine on `render/` CPU-surface output.
- **Visual checks**: `uv run python scripts/screenshot_app.py` renders the window offscreen (`QT_QPA_PLATFORM=offscreen`) with demo shapes (`--empty` for none) and saves `dev-screenshots/app.png` (gitignored). Read the PNG; crop/zoom small regions with Pillow (dev dep via pytablericons) before reading when checking fine detail. Delete scratch crops after use.
- For interaction checks, drive the real window headless with `PySide6.QtTest.QTest` (mouse press/move/release on `canvas.viewport()`, doc → screen via `canvas._vp.to_screen`) in a scratch script; run once offscreen (raster) and once on the desktop (GL). Don't add whole-window pixel assertions to the pytest suite.
- Canvas performance: `uv run python scripts/bench_canvas.py` (10k shapes; `PRESSTOSHAPE_RENDERER=cpu` for the raster path).
- SVG conformance (`docs/svg-conformance.md`): `uv run python scripts/svg_conformance.py fetch` once, then `report` (HTML with side-by-side images in `build/svg-conformance/`). `tests/scripts/svg_conformance_pass.txt` is checked by pytest while the suite is fetched; add a test only after comparing it by eye, keep reviewed-but-wrong ones as `!name # reason`, never drop an entry to make a change pass without saying so. Saved SVG is also rendered by resvg (dev dep) and must match our canvas (`tests/formats/test_svg_generator.py`).
