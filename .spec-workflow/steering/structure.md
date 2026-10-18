# Project Structure

## Directory Organization

Grouped by layer (Model / View / Controller), one module per concern inside each layer.

```
veccy/                          # repo root
├── main.py                     # thin entry point: sys.exit(App().run())
├── pyproject.toml / uv.lock    # uv project, pinned deps (lockfile committed)
├── .python-version             # CPython floor for uv
├── .mcp.json                   # spec-workflow MCP server (pinned version)
├── .spec-workflow/             # steering docs, specs, templates (committed)
├── README.md / CLAUDE.md       # user-facing overview / contributor + agent rules
├── scripts/                    # dev tools, never imported by the app
│   ├── screenshot_app.py       # offscreen window render -> dev-screenshots/app.png
│   ├── generate_icons.py       # copies Tabler SVGs from pytablericons into veccy/assets/icons
│   └── spec_dashboard.sh       # starts the spec-workflow dashboard
├── tests/                      # pytest, Qt-free logic only
│   └── test_<module>.py
└── veccy/                      # application package
    ├── app.py                  # App: creates AppState + AppController + MainWindow, owns QApplication
    ├── icons.py                # semantic icon path constants
    ├── assets/icons/*.svg      # generated Tabler outline icons (currentColor)
    ├── models/                 # plain dataclasses, no logic beyond defaults
    │   ├── app_state.py        # AppState, Document, Layer, Tool
    │   └── shapes.py           # frozen shapes, Style, path segments
    ├── controllers/            # all state mutation + pure logic, no Qt
    │   ├── app_controller.py   # mutations, undo/redo, file I/O, subscribe/notify
    │   ├── geometry.py         # pure geometry + boolean ops (skia-pathops)
    │   └── svg_io.py           # SVG read/write
    └── views/                  # Qt widgets
        ├── main_window.py      # assembles panels, fans out refresh(), owns dialogs
        ├── actions.py          # every QAction, shared by menus and toolbars
        ├── canvas_view.py      # QGraphicsView: scene sync from model, gestures -> controller
        ├── *_view.py           # one panel/bar per module (layers, tool options, selection, toolbar, …)
        ├── style_editor.py / widgets.py   # reusable widgets
        ├── theme.py            # palette, colors, stylesheet
        └── icon_engine.py      # SvgIconEngine (vector icons, currentColor recoloring)
```

Planned additions (each introduced by its own spec):
```
veccy/
├── render/                     # Skia renderer: model -> skia.Canvas. Depends on models only, no Qt.
│                               # Shared by the canvas (via a thin Qt surface in views/) and raster export.
├── controllers/
│   ├── <format>_io.py          # native document format read/write, next to svg_io.py
│   └── <feature>.py            # pure logic per feature (brushes, effects, text layout, …)
└── views/
    └── tools/                  # per-tool gesture handlers, once canvas_view.py outgrows one module
```

## Naming Conventions

### Files
- **Modules**: `snake_case.py`.
- **Views**: panels and bars as `<name>_view.py` (`layers_view.py`, `tool_options_view.py`); shared widgets/helpers by purpose (`style_editor.py`, `widgets.py`, `theme.py`).
- **Controllers**: by responsibility (`app_controller.py`, `geometry.py`); file formats as `<format>_io.py`.
- **Tests**: `tests/test_<module>.py`, one per tested module; test functions `test_<behavior>` describing the expected behavior (`test_tiny_drag_adds_nothing`).

### Code
- **Classes/Types**: `PascalCase`. Shapes end in `Shape` (`RectShape`); Qt panels end in `Panel`/`View`/descriptive widget names (`LayersPanel`, `CanvasView`, `StyleEditor`).
- **Functions/Methods**: `snake_case`. Controller methods are verbs on the domain (`add_rectangle`, `move_selection`, `set_layer_visible`); views expose `refresh(state)`.
- **Constants**: `UPPER_SNAKE_CASE`; module-private with a leading underscore (`_UNDO_LIMIT`, `_WHEEL_ZOOM`).
- **Variables**: `snake_case`; private members/helpers with a leading underscore.
- **Type aliases**: `PascalCase` (`Shape`, `Segment`, `Point`, `Matrix`).

## Import Patterns

### Import Order
1. Standard library
2. Third-party (`PySide6`, `skia-pathops`, `svgelements`, …)
3. Internal `veccy.*` modules

Groups separated by a blank line (ruff `I` / isort order once ruff is added).

### Module/Package Organization
- Absolute imports with the `veccy.` prefix everywhere (`from veccy.models.app_state import AppState`); no relative imports.
- Dependency direction is strict: `views → controllers → models` (planned `render` sits beside controllers: `views → render → models`). Never import a view from a model, controller or renderer.
- **No Qt imports in `models/`, `controllers/` or `render/`.**
- PySide6 only — never PyQt5/6.
- Dev-only packages (`pytablericons`, `pytest`) are never imported by `veccy/`.

## Code Structure Patterns

### Module/Class Organization
1. Module docstring only when it explains a non-obvious *why* or contract
2. Imports
3. Module constants (`_PRIVATE` tuning values, lookup tables)
4. Small private helpers
5. Main class(es) / public functions

Large classes are sectioned with `# --- section ---` comments (e.g. `# --- undo ---`, `# --- queries ---` in `AppController`).

### Function/Method Organization
- **Controller mutations**: validate / early-return on no-op input → `self._checkpoint(merge_key)` before mutating the document → mutate via `dataclasses.replace` → set `status_message` → `self._notify()`. Notify even on rejected input when a view needs to revert.
- **View `refresh(state)`**: idempotent and cheap; skip work when the relevant slice of state is unchanged; `blockSignals(True)` while writing values back into widgets.
- **Gestures**: transient state lives in view attributes until the gesture commits through one controller call.
- **Signals**: connect `triggered` / `clicked` via `lambda: slot()` so the `checked` bool doesn't land in an optional parameter.
- Error handling only at real I/O boundaries (file load/save, parsing foreign files); no defensive try/except around Qt calls.

### File Organization Principles
- One panel/view class per module; reusable widgets in shared modules.
- Pure logic goes in controllers (or `render/`) with tests, not in views.
- New state goes into nested dataclasses in `models/` per feature — no module-level state or singletons; one `AppState` passed explicitly.
- Dialogs (file pickers, confirmations, text input) live in views; controllers receive plain values.

## Code Organization Principles

1. **Single source of truth**: `AppState` holds all persistent app state; views render from it, controllers alone write it.
2. **Immutability**: shapes and geometry are frozen dataclasses; undo snapshots share them.
3. **Testability**: everything not inherently Qt lives Qt-free and is covered by pytest.
4. **Single responsibility**: one clear purpose per module.
5. **Consistency**: follow existing patterns (controller method shape, `refresh(state)`, icon loading via `icon_engine.icon(path)`).

## Module Boundaries
- **Models**: data only. No imports from controllers, views or Qt.
- **Controllers**: the only code that mutates `AppState`. Pure functions for geometry/I/O; `AppController` is the façade views call. No Qt.
- **Render (planned)**: pure model → Skia drawing; no state mutation, no Qt. Used by the canvas surface and exporters, guaranteeing canvas = export.
- **Views**: Qt only; read state, call controllers. Own transient gesture state, dialogs and Qt object lifetimes (parents set, signals disconnected on teardown — see `CanvasView.shutdown()`).
- **Scripts / tests**: may import anything from `veccy`; nothing in `veccy` imports them.
- **Assets**: generated files in `veccy/assets/` are only changed by their generator scripts.

## Code Size Guidelines
- **File size**: aim for ≤ ~400 lines; split by responsibility before going past it (current largest: `app_controller.py` ≈ 400, `canvas_view.py` ≈ 350 — next candidates for splitting, e.g. per-tool gesture handlers, per-feature controller modules).
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
