# Technology Stack

## Project Type
Desktop application for Linux and Windows (macOS not a target for now): a professional vector drawing tool written in Python with a Qt 6 Widgets UI. Distributed as packaged, installable builds; developed and run from source with `uv`.

## Core Technologies

### Primary Language(s)
- **Language**: Python, `requires-python >= 3.13` (`.python-version`: 3.13). The floor is concrete because PySide6 wheels trail new CPython releases.
- **Runtime**: CPython.
- **Language-specific tools**: `uv` for everything — dependencies (`uv add`, `uv add --dev`), running (`uv run python main.py`), syncing (`uv sync`). `uv.lock` is committed and never hand-edited. No bare `pip` / `venv`.

### Key Dependencies/Libraries
- **pyside6-essentials (==6.12.0, pinned)**: Qt 6 bindings — QtCore/QtGui/QtWidgets/QtOpenGLWidgets/QtSvg/QtTest. UI, input, GL context hosting. Pinned with `==` because Qt behavior and binding details shift between minors. `pyside6-essentials`, not the `pyside6` metapackage (WebEngine/addons, hundreds of MB, unused).
- **skia-pathops (0.9.2)**: boolean path operations (union, difference, intersection, XOR; divide and region splitting built on them) in `presstoshape/geometry/booleans.py`. Works in float32; results are rounded on conversion.
- **svgelements (1.9.6)**: parsing SVG path data, colors, lengths and transform strings only. Its `SVG.parse` document reader is not used — it drops `display:none` groups (hidden layers) and `<text>`. Document traversal uses `xml.etree.ElementTree`.
- **skia-python (==144.0.post2)**: canvas and PNG export renderer (`presstoshape/render/`), GPU via OpenGL, CPU raster fallback (see Decision Log).
- **Dev only**: `pytest` (tests), `pytablericons` (source of Tabler icon SVGs, copied by `scripts/generate_icons.py`; never imported by the running app). Planned: `ruff`, a static type checker, `pyinstaller`.

### Application Architecture
Session / operations / tools / views, as in professional editors (Blender's operators, Krita's commands, Inkscape's verbs), with Elm-like state ownership inside Qt's retained-mode widgets:

- **Models** (`presstoshape/models/`): plain dataclasses. `AppState` (document, active tool, selection, node selection, tool styles, zoom, file path, dirty flag) is the single source of truth. Shapes and path segments are **frozen** dataclasses changed via `dataclasses.replace`.
- **Geometry** (`presstoshape/geometry/`) and **formats** (`presstoshape/formats/`): pure functions over models — affine math, segments, booleans, shape transforms, node editing; SVG read/write. Composites are saved as their result path plus a definition in `<metadata>` (namespace `https://github.com/blindpenguin/presstoshape/ns/svg/1`), checked geometrically on load.
- **Render** (`presstoshape/render/`): Skia drawing of the model — document, overlays, picking (shapes, handles, nodes), viewport math, PNG export.
- **Session** (`presstoshape/editing/session.py`): owns the one `AppState`, the undo history with labelled steps and the subscriber list. `with session.edit("Label"):` records one undo step, marks the document dirty and notifies once.
- **Operations** (`presstoshape/editing/operations/`): the only code that changes state — plain functions `operation(session, ...)`, one module per feature. Commands that need no extra input are registered (`presstoshape/editing/registry.py`: id, menu label, "can run?" check), so menus, shortcuts and later a command search or scripting API come from one list.
- **Tools** (`presstoshape/tools/`): Qt-free input state machines (`BaseTool` subclasses, listed in `tools/registry.py`). They hold gesture state and previews and commit through one operation call.
- **Views** (`presstoshape/views/`): Qt widgets. They render from state in an idempotent, cheap `refresh(state)`; menus and toolbars are built from the registries plus `views/keymap.py` (shortcuts, icons, layouts); `CanvasView` forwards input to the active tool. Dialogs live here and pass plain values to operations.
- **Data flow**: input → tool/view → operation → `session.edit()` (undo, mutate `AppState`) → `session.notify()` → `MainWindow.refresh()` → every view's `refresh(state)`.
- **Dependency direction**: `models ← geometry ← render ← editing ← tools ← views`; `formats` uses only models and geometry; `editing` may use formats and render. **No Qt below views.** Enforced by `tests/test_architecture.py`.
- **Canvas**: `CanvasView` (QAbstractScrollArea) hosts a Skia surface widget and redraws the document from state each frame, replaying recorded Skia pictures. Shape geometry is in document coordinates with a canonical per-shape transform.
- **Undo**: snapshot-based, behind `Session.edit`. Snapshots copy layer lists and share immutable shape objects; consecutive edits with the same merge key collapse into one step; 200-step limit. Steps carry labels shown in the Edit menu.

### Data Storage (if applicable)
- **Primary storage**: local files.
- **Native format (planned)**: a PressToShape document format that stores everything PressToShape supports losslessly. Requirements: versioned with forward migration, exact reload of what was saved, able to embed resources (images, fonts as needed). Concrete format (e.g. zip + JSON, SQLite) is decided in its own spec.
- **SVG**: import/export for exchange. Writes SVG with Inkscape layer groups (`inkscape:groupmode="layer"`, `inkscape:label`). Reads general SVG; rect/ellipse/text keep rotate/scale/skew transforms as a per-shape `transform` (written back as `rotate(...)` or `matrix(...)`), paths get transforms applied to their points; unsupported paint is approximated.
- **Raster export**: PNG, rendered by the same renderer as the canvas (transparent background, any scale up to 16384 px per side).
- **Caching**: in-memory only (Skia path cache and recorded document pictures in the canvas).

### External Integrations (if applicable)
None. PressToShape is offline; no network access, accounts or telemetry. Interop is file-based (SVG, raster export, later PDF/AI-compatible import).

## Development Environment

### Build & Development Tools
- **Build System**: none for development — `uv run python main.py`. Packaging via **PyInstaller** (planned) for per-OS bundles.
- **Package Management**: `uv` with committed `uv.lock`.
- **Development workflow**:
  - `uv run pytest` — logic tests.
  - `uv run python scripts/screenshot_app.py` — renders the window offscreen (`QT_QPA_PLATFORM=offscreen`) to `dev-screenshots/app.png` for visual checks.
  - Interaction checks: scratch scripts driving the real window headless with `PySide6.QtTest.QTest`.
  - `uv run --group dev python scripts/generate_icons.py` — regenerate icons.
  - `scripts/spec_dashboard.sh` — spec-workflow approval dashboard.

### Code Quality Tools
- **Static Analysis**: `ruff check` (planned) and a static type checker — mypy or pyright, chosen when adding it. Code is already fully type-annotated.
- **Formatting**: `ruff format` (planned).
- **Testing Framework**: `pytest` for everything below views (models, geometry, formats, render, editing, tools), mirrored in `tests/<package>/`; an architecture test enforces the layer rules. No pixel assertions in the suite; visual/interaction checks are done with offscreen screenshots and QTest scratch scripts.
- **Documentation**: `README.md` (features, dev commands), `CLAUDE.md` (agent/contributor rules), spec-workflow steering docs and specs in `.spec-workflow/`.

### Version Control & Collaboration
- **VCS**: Git.
- **Branching Strategy**: feature branches + pull requests for spec-driven features and larger changes (one spec → one branch → one PR, e.g. `feat/brush-tool`). Small fixes may go directly to `main` while the project has a single maintainer. `main` should always be green.
- **CI (planned)**: GitHub Actions — ruff, type check and pytest on Linux and Windows for every PR and push to `main`; PyInstaller builds per OS for releases.
- **Code Review Process**: PRs are reviewed before merge; CI must pass.
- **Feature process**: spec-workflow MCP (`@pimzino/spec-workflow-mcp`, pinned version in `.mcp.json`) — Requirements → Design → Tasks, each approved in the dashboard, then task-by-task implementation with logs.

## Deployment & Distribution (if applicable)
- **Target Platform(s)**: desktop — Linux and Windows. Development and testing happen on Linux; Windows is untested until CI or a Windows machine is available. macOS is not a target for now (it may run, with limitations: no Metal backend in skia-python, deprecated OpenGL).
- **Distribution Method**: packaged builds (PyInstaller bundles per OS) published as release downloads; running from source with `uv` for developers.
- **Installation Requirements**: none beyond the bundle for end users; for source: `uv` and a supported CPython.
- **Update Mechanism**: manual download of new releases (no auto-updater planned yet).
- **License**: GPL-3.0 (compatible with PySide6 LGPL and BSD-licensed Skia libraries).

## Technical Requirements & Constraints

### Performance Requirements
- Fluid pan/zoom/drag and brush strokes (no visible lag) on documents with tens of thousands of shapes.
- Freehand/brush input must keep up with tablet event rates, with pressure.
- Usable window within a couple of seconds of launch.
- `refresh(state)` stays cheap: views skip rebuilds when their slice of state is unchanged.

### Compatibility Requirements
- **Platform Support**: Linux and Windows (x86_64 and arm64 where wheels exist).
- **Dependency Versions**: PySide6 pinned exactly; other runtime deps pinned in `pyproject.toml`/`uv.lock`; Python floor follows PySide6 wheel availability.
- **Standards Compliance**: SVG 1.1/2 for import/export; Inkscape layer conventions; canvas rendering matches SVG semantics (nonzero fill rule, flat cap, miter join defaults).

### Security & Compliance
- **Security Requirements**: files are untrusted input — SVG/native-format parsing must not execute content, fetch external resources or crash on malformed input; errors are reported, not raised to the user as tracebacks.
- **Compliance Standards**: GPL-3.0 obligations for distribution; bundled dependency licenses included in packaged builds.
- **Threat Model**: malicious or malformed files (XML bombs, huge dimensions, deep nesting).

### Scalability & Reliability
- **Expected Load**: single user, local; documents up to tens of thousands of shapes.
- **Reliability**: no data loss — every edit undoable, saves lossless in the native format; future: autosave/crash recovery.

## Technical Decisions & Rationale

### Decision Log
1. **PySide6 (Qt 6 Widgets)**: mature cross-platform desktop UI with tablet input, high-DPI and native dialogs; official Qt binding under LGPL. Never mixed with PyQt (incompatible objects).
2. **Session / operations / tools / views with single-source-of-truth state, no Qt below views**: the shape professional editors use. Every edit is a named operation running through one session (undo and refresh for free, one place to change undo or notification later); tools are separate input state machines; menus and shortcuts come from registries. Keeps logic unit-testable without a display and rendering a pure function of state. Trade-off: rendering must stay fast enough to redraw from state (path cache, recorded pictures). Replaced an earlier MVC layout whose controller had grown into one large class.
3. **Frozen shape dataclasses + snapshot undo**: snapshots are cheap (shared immutable shapes), undo is trivially correct, views diff by equality. Trade-off: every edit replaces objects; snapshot cost grows with layer/shape count.
4. **Commit to Skia for rendering (skia-python)**: QPainter/QGraphicsScene can't deliver the target feature set at scale — mesh gradients, blend modes, live effects (blur, shadows, filters), variable-width brush strokes, GPU acceleration. Skia is the renderer behind Chrome and many design tools, already used here via skia-pathops, and the same renderer serves canvas and raster/PDF export (WYSIWYG). Plan: keep Qt for UI and input; render the canvas with Skia (GPU via an OpenGL surface, CPU raster fallback); the renderer boundary is `presstoshape/render/` (implemented by the skia-renderer spec).
5. **Own native format + SVG for exchange**: SVG can't hold everything PressToShape will support (live effects, brush definitions, editable booleans); a native format guarantees fidelity, while SVG export degrades predictably (flatten/rasterize) and keeps Inkscape interop. Format choice deferred to a spec.
6. **skia-pathops for booleans**: robust, fast, Qt-free. Float32 precision accepted; results rounded.
7. **svgelements for SVG micro-syntax only, ElementTree for documents**: svgelements' document reader loses hidden layers and text.
8. **SVG icons with a custom `SvgIconEngine`**: vector icons at any DPI, recolored per mode/state; Qt's default SVG icon engine leaves `currentColor` black.
9. **uv + exact pins**: reproducible environments; Qt minor upgrades are deliberate.
10. **PyInstaller for packaging**: mature, supports PySide6 on Linux and Windows.
11. **GPL-3.0**: protects against closed-source forks, in line with Inkscape/Krita.

## Known Limitations
- **Renderer**: Skia renders shapes with solid paint only so far; gradients, blend modes and effects are future specs. Continuous zoom on documents with many text objects re-rasterizes glyphs at each scale (~20 ms/frame at 10k shapes on an integrated GPU); pan and drag stay under 16 ms. The CPU fallback is ~25–30 ms/frame at 10k shapes.
- **Undo scaling**: snapshot undo copies every layer's shape list per step — fine now, may need structural sharing or command-based undo for very large documents (a change inside `Session`, operations stay as they are).
- **Full-state notify**: every change refreshes every view; views must keep diffing cheap, and finer-grained change notification may be needed as the UI grows.
- **SVG import gaps**: gradients, clip paths, masks, `<use>`, images and CSS stylesheets are skipped or approximated; skew on text is dropped.
- **Text**: single-line, single font; rendered with Skia using a generic sans-serif font.
- **Shape model**: no groups. Each shape has an affine `transform`, kept canonical: rect/ellipse/text store unrotated geometry plus a rotation about their center (a full matrix only when skewed); paths always have the transform baked into their segments. Handle scaling changes geometry, so strokes don't scale.
- **No native format, no packaging or CI yet**.
