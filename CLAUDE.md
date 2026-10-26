# PressToShape — agent rules

Python SVG editor built on [PySide6](https://doc.qt.io/qtforpython-6/) (Qt 6 Widgets) with a Skia-rendered canvas. Managed with `uv`.

Folder-specific rules live in nested `CLAUDE.md` files, loaded when you work there: `presstoshape/{views,render,editing,tools,formats,geometry}/` and `packaging/` (nightlies, `scripts/build_package.py`, `.github/workflows/`).

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
- **skia-pathops** — boolean path ops in `presstoshape/geometry/booleans.py`.
- **svgelements** — only for parsing SVG values (path `d`, colors, lengths, transforms) in `formats/`; never its document reader.

## Architecture: session, operations, tools, views

Structured like professional editors (Blender, Krita, Inkscape): one state, edits as named operations, tools that turn input into operations, views that re-render from state. Qt is retained-mode, but state ownership stays Elm-like.

```
main.py              # thin: sys.exit(App().run())
presstoshape/
├── app.py           # resolves + installs the language, creates the Session + MainWindow, owns QApplication; --self-test
├── i18n/            # translations, Qt-free bottom layer: _ / ngettext / pgettext / N_, PO parser, plural formulas, catalogs
├── version.py       # app version (build stamp or pyproject.toml)
├── icons.py         # semantic icon path constants (views only)
├── models/          # plain data: app_state.py (AppState, Document, Layer, Tool), shapes.py (frozen)
├── geometry/        # pure shape math, no state
├── formats/         # SVG read/write, native .p2s, clipboard payload, image probing
├── render/          # Skia drawing: model -> skia.Canvas, hit-testing, viewport
├── editing/         # Session (state, undo, notify), operation registry, queries, containers, operations/
├── tools/           # Qt-free input state machines
└── views/           # Qt widgets only
```

Rules:
- Import direction: `models <- geometry <- render <- editing <- tools <- views`; `formats` uses only models + geometry; `editing` may use formats and render (export, text outlines). `i18n` is below everything and importable from every layer. `tests/test_architecture.py` enforces it.
- **No Qt below `views/`** (models, geometry, formats, render, editing, tools). That keeps them unit-testable without a display. `render/` can't see `views/theme.py`; views pass colors in (`CanvasColors`).
- Import with the `presstoshape.` prefix everywhere (`from presstoshape.models.app_state import AppState`).
- Data flow: input → tool or view → operation function → `session.edit(label)` records undo and mutates `AppState` → `session.notify()` → `MainWindow.refresh()` → every view's `refresh(state)`. Views and tools never assign to `AppState`.
- Operations are plain functions `operation(session, ...)` in `editing/operations/<feature>.py`. Document edits go inside `with session.edit("Label"):` (one undo step, named in the Undo menu; `merge_key` merges spinbox steps). Non-document changes (selection, tool, zoom) mutate and call `session.notify()`. Notify even on rejected input when a view needs to revert (e.g. `rename_layer`). Operations take plain values; dialogs stay in views.
- Groups and Composites are containers: operations reach "the shapes being edited" only through `editing/containers.py`, never `layer.shapes` directly (details in `editing/CLAUDE.md`; `tests/test_conventions.py` lists the allowed exceptions).
- `ImageShape` is a leaf with a shared `ImageData` blob (original file bytes, equality by digest; decoded lazily in `render/images.py`). It has no `style` either (only `opacity`), so code that reads `shape.style` handles images too; booleans, Composites and clip objects refuse them.
- `GroupShape` has no `style` and an identity transform: code that reads `shape.style` or recurses into shapes handles groups first (drawing, hit-testing, bounds, styling through `style.restyle_shape`, encoders).
- Shapes are frozen; change them with `dataclasses.replace`. Undo snapshots copy layer lists only and share shape objects.
- Coordinates are document pixels (1/`Document.dpi` inch) everywhere below the views. `Document.unit` only changes how lengths are shown and entered: convert at the widget boundary (`views/unit_fields.LengthSpinBox`, `geometry/units`), never in operations, geometry or rendering.
- Shape `transform` stays canonical: go through `geometry.transforms` (`transform_shape`, `translate`, `with_rotation`) rather than composing matrices onto shapes by hand. Paths keep an identity transform (baked into segments).
- A path's segments are its nodes; what is drawn is `transforms.outline` (it rounds live corners, `geometry/corners.py`). Code that draws, measures or combines a path goes through `outline` / `area_outline`, never `path.segments` directly; node editing works on the segments.
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

## Packaging

- Nightlies, PyInstaller, WiX and `scripts/build_package.py`: see `packaging/CLAUDE.md`.
- `main.py --self-test` is the headless smoke check every build must pass; extend it when adding something a frozen bundle could miss (new data files, plugins, native libraries).

## Testing

- Lint and format with ruff (config in `pyproject.toml`: line length 120, rules `E`/`F`/`I`, `.spec-workflow/` excluded): `uv run ruff check .` and `uv run ruff format .`. Run both before finishing a change; the formatter owns line wrapping, so don't hand-wrap.
- Everything below `views/` is tested with `pytest`: `uv run pytest`. Tests mirror the package layout (`tests/editing/test_layers.py`, `tests/tools/test_select.py`, …); shared helpers live in `tests/helpers.py` (`ToolDriver`, `all_shapes`), the `session` fixture in `tests/conftest.py`. New logic goes there with tests. Pixel assertions are fine on `render/` CPU-surface output.
- Visual and interaction checks of the real window: `presstoshape/views/CLAUDE.md`. Canvas benchmark: `presstoshape/render/CLAUDE.md`. SVG conformance: `presstoshape/formats/CLAUDE.md`.
