# Project Structure

## Directory Organization

Grouped by layer, one module per concern inside each layer. Layers, bottom to top: models → geometry / formats → render → editing (session + operations) → tools → views.

```
presstoshape/                   # repo root
├── main.py                     # thin entry point: sys.exit(App().run())
├── pyproject.toml / uv.lock    # uv project, pinned deps (lockfile committed)
├── .python-version             # CPython floor for uv
├── .mcp.json                   # spec-workflow MCP server (pinned version)
├── .spec-workflow/             # steering docs, specs, templates (committed)
├── .github/workflows/          # nightly.yml: nightly builds and the rolling "nightly" pre-release
├── packaging/                  # static packaging inputs: PyInstaller spec, WiX source, AppImage files, licenses
├── README.md / CLAUDE.md       # user-facing overview / contributor + agent rules
├── scripts/                    # dev tools, never imported by the app
│   ├── screenshot_app.py       # offscreen window render -> dev-screenshots/app.png
│   ├── bench_canvas.py         # canvas frame times on a 10k-shape document
│   ├── generate_icons.py       # copies Tabler SVGs from pytablericons into presstoshape/assets/icons
│   ├── build_package.py        # builds nightly packages (AppImage, MSI, portable ZIP, source), locally and in CI
│   └── spec_dashboard.sh       # starts the spec-workflow dashboard
├── tests/                      # pytest, Qt-free code only; mirrors the package layout
│   ├── conftest.py / helpers.py   # `session` fixture; ToolDriver, all_shapes, bbox, …
│   ├── test_architecture.py    # layer and Qt-free rules
│   └── geometry/ formats/ render/ editing/ tools/ views/   # test_<module>.py per module
└── presstoshape/               # application package
    ├── app.py                  # App: creates the Session + MainWindow, owns QApplication
    ├── icons.py                # semantic icon path constants (views only; app for the window icon)
    ├── version.py              # app version: build stamp (_build_info.py, generated) or pyproject.toml
    ├── assets/icons/*.svg      # generated Tabler outline icons (currentColor)
    ├── models/                 # plain dataclasses, no logic beyond defaults
    │   ├── app_state.py        # AppState, Document, Layer, Tool
    │   └── shapes.py           # frozen shapes (incl. CompositeShape), Style, path segments, Transform
    ├── geometry/               # pure shape math
    │   ├── affine.py           # 2D affine math on (a, b, c, d, e, f) tuples
    │   ├── boxes.py            # Point, Rect, drag boxes
    │   ├── segments.py         # building/mapping path segments
    │   ├── booleans.py         # ordered-parts booleans, divide, regions (skia-pathops)
    │   ├── transforms.py       # outline, translate, canonical shape transforms
    │   └── nodes.py            # path node editing (move, smooth handles, insert, delete)
    ├── formats/
    │   └── svg.py              # SVG read/write
    ├── render/                 # Skia drawing: scene, picture, paths, text, hit_test, handles, viewport, export, overlay
    ├── editing/
    │   ├── session.py          # Session: AppState, labelled undo history, notify, edit()
    │   ├── registry.py         # Operation table: id, menu label, can_run
    │   ├── queries.py          # read-only questions about state
    │   ├── containers.py       # active container (layer or entered Composite chain via edit_path)
    │   └── operations/         # history, view, selection, shapes, transform, booleans, composites, arrange, paths, node_editing, style, layers, documents
    ├── tools/
    │   ├── base.py             # Mods, CursorType, ToolContext, BaseTool
    │   ├── registry.py         # TOOLS + Toolbox
    │   └── select.py / node.py / pen.py / shapes.py / text.py
    └── views/                  # Qt widgets only
        ├── main_window.py      # assembles panels, fans out refresh(), window commands (dialogs)
        ├── keymap.py           # shortcuts, icons, menu/toolbar layouts per command id
        ├── actions.py          # QActions built from the registries + keymap
        ├── canvas_view.py      # scroll area + Skia surface: zoom/pan, forwards input to the active tool
        ├── cursors.py          # CursorType -> QCursor (custom SVG rotate / node-insert cursors)
        ├── skia_surface.py     # GL / raster Skia surface widgets
        ├── *_view.py           # one panel/bar per module (layers, tool options, selection, toolbar, …)
        ├── style_editor.py / widgets.py   # reusable widgets
        ├── theme.py            # palette, colors, stylesheet
        └── icon_engine.py      # SvgIconEngine (vector icons, currentColor recoloring)
```

Planned additions (each introduced by its own spec):
```
presstoshape/
├── formats/<format>.py         # native document format, next to svg.py
├── geometry/<topic>.py         # more pure math (offset, simplify, brush outlines, …)
├── editing/operations/<feature>.py   # new commands
└── tools/<tool>.py             # new tools (pencil, brush, gradient, …)
```

## Naming Conventions

### Files
- **Modules**: `snake_case.py`.
- **Views**: panels and bars as `<name>_view.py` (`layers_view.py`, `tool_options_view.py`); shared widgets/helpers by purpose (`style_editor.py`, `widgets.py`, `theme.py`).
- **Operations**: one module per feature in `editing/operations/` (`layers.py`, `node_editing.py`); tools one module per tool or family in `tools/`; file formats as `formats/<format>.py`.
- **Tests**: `tests/<package>/test_<module>.py`, mirroring the package layout; test functions `test_<behavior>` describing the expected behavior (`test_tiny_drag_adds_nothing`).

### Code
- **Classes/Types**: `PascalCase`. Shapes end in `Shape` (`RectShape`); Qt panels end in `Panel`/`View`/descriptive widget names (`LayersPanel`, `CanvasView`, `StyleEditor`).
- **Functions/Methods**: `snake_case`. Operations are verbs on the domain taking the session first (`add_rectangle(session, ...)`, `move_selection`, `set_layer_visible`); views expose `refresh(state)`.
- **Command ids**: dotted `<area>.<command>` (`edit.delete`, `path.object_to_path`, `tool.node`), shared by registries and the keymap.
- **Names**: speaking but not overlong (`session`, `shape`, `segments`, `frame`; short names only for math and tiny scopes); say "type", not "kind".
- **Constants**: `UPPER_SNAKE_CASE`; module-private with a leading underscore (`_UNDO_LIMIT`, `_WHEEL_ZOOM`).
- **Variables**: `snake_case`; private members/helpers with a leading underscore.
- **Type aliases**: `PascalCase` (`Shape`, `Segment`, `Point`, `Rect`, `Affine`).

## Import Patterns

### Import Order
1. Standard library
2. Third-party (`PySide6`, `skia-pathops`, `svgelements`, …)
3. Internal `presstoshape.*` modules

Groups separated by a blank line (ruff `I` / isort order once ruff is added).

### Module/Package Organization
- Absolute imports with the `presstoshape.` prefix everywhere (`from presstoshape.models.app_state import AppState`); no relative imports.
- Dependency direction is strict: `models ← geometry ← render ← editing ← tools ← views`; `formats` uses only models and geometry; `editing` may use formats and render. `tests/test_architecture.py` enforces it.
- **No Qt imports below `views/`.**
- PySide6 only — never PyQt5/6.
- Dev-only packages (`pytablericons`, `pytest`) are never imported by `presstoshape/`.

## Code Structure Patterns

### Module/Class Organization
1. Module docstring only when it explains a non-obvious *why* or contract
2. Imports
3. Module constants (`_PRIVATE` tuning values, lookup tables)
4. Small private helpers
5. Main class(es) / public functions

Large classes are sectioned with `# --- section ---` comments (e.g. `# --- editing ---`, `# --- undo / redo ---` in `Session`).

### Function/Method Organization
- **Operations**: validate / early-return on no-op input → `with session.edit("Label", merge_key):` → mutate via `dataclasses.replace` and the `_document` helpers → set `status_message`. Non-document changes mutate and call `session.notify()`. Notify even on rejected input when a view needs to revert. Register with `@operation(id, label, can_run)` when a menu or shortcut can run it without extra input.
- **View `refresh(state)`**: idempotent and cheap; skip work when the relevant slice of state is unchanged; `blockSignals(True)` while writing values back into widgets.
- **Tools**: subclass `BaseTool`; transient gesture state lives in the tool until it commits through one operation call; list new tools in `tools/registry.py`.
- **Signals**: connect `triggered` / `clicked` via `lambda: slot()` so the `checked` bool doesn't land in an optional parameter.
- Error handling only at real I/O boundaries (file load/save, parsing foreign files); no defensive try/except around Qt calls.

### File Organization Principles
- One panel/view class per module; reusable widgets in shared modules.
- Pure logic goes in `geometry/`, `render/`, `editing/` or `tools/` with tests, not in views.
- New state goes into nested dataclasses in `models/` per feature — no module-level state or singletons; one `Session` (owning the `AppState`) passed explicitly. Registries hold definitions only.
- Dialogs (file pickers, confirmations, text input) live in views; operations receive plain values.

## Code Organization Principles

1. **Single source of truth**: `AppState` holds all persistent app state; views render from it, operations alone write it, through the session.
2. **Immutability**: shapes and geometry are frozen dataclasses; undo snapshots share them.
3. **Testability**: everything not inherently Qt lives Qt-free and is covered by pytest.
4. **Single responsibility**: one clear purpose per module.
5. **Consistency**: follow existing patterns (operation shape with `session.edit`, `BaseTool`, `refresh(state)`, icon loading via `icon_engine.icon(path)`).

## Module Boundaries
- **Models**: data only. No presstoshape or Qt imports.
- **Geometry / formats**: pure functions over models; no state.
- **Render**: pure model → Skia drawing, picking and viewport math; no state mutation. Used by the canvas surface and exporters, guaranteeing canvas = export.
- **Editing**: the session and the operations — the only code that changes `AppState`.
- **Tools**: input state machines; read state, call operations; no Qt.
- **Views**: Qt only; read state, call operations, forward canvas input to the active tool. Own dialogs, the keymap and Qt object lifetimes (parents set, signals disconnected on teardown — see `CanvasView.shutdown()`).
- **Scripts / tests**: may import anything from `presstoshape`; nothing in `presstoshape` imports them.
- **Assets**: generated files in `presstoshape/assets/` are only changed by their generator scripts.

## Code Size Guidelines
- **File size**: aim for ≤ ~400 lines; split by responsibility before going past it (current largest: `geometry/nodes.py` and `formats/svg.py` ≈ 350).
- **Function/Method size**: aim for ≤ ~40 lines; extract helpers for distinct steps.
- **Nesting depth**: ≤ 3 levels; prefer early returns and `match` on shape/segment types.
- **Line length**: 120 characters.

## Dashboard/Monitoring Structure (if applicable)
Not part of the app. The spec-workflow dashboard is an external dev tool started via `scripts/spec_dashboard.sh`; its data lives in `.spec-workflow/` and the app never depends on it.

## Documentation Standards
- Default: no comments. Add one only for a non-obvious *why* (e.g. Qt quirks, SVG semantics, float precision).
- Short docstrings on classes/functions whose contract isn't obvious from the name and types.
- Full type annotations on all functions and dataclass fields.
- `README.md`: user-facing features and dev commands — update when features change.
- `CLAUDE.md`: contributor/agent rules, Qt pitfalls, architecture — update when a new convention or pitfall is established.
- Feature design and decisions: spec-workflow specs in `.spec-workflow/specs/`.
