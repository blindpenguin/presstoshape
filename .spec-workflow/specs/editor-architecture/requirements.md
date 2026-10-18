# Requirements Document

## Introduction

veccy's code is described as MVC, but in practice it already works like professional editors (Blender, Krita, Inkscape): one document state, edits that run through a single writer, tools that turn mouse input into edits, and views that re-render from state. The names and package layout don't say so, which causes concrete problems:

- `controllers/` mixes stateful command code (`AppController`) with pure math (`geometry.py`, `affine.py`, `nodes.py`) and file I/O (`svg_io.py`). `render/` imports from `controllers/`, against the documented dependency rule.
- `AppController` is 555 lines covering eight concerns (undo, queries, tools, creation, selection/transforms, nodes, style, layers, files), over the ~400-line guideline.
- Every menu and toolbar action is wired by hand in `views/actions.py`; labels, enabled checks and shortcuts are spread out, and there is no single list of commands to build menus, a command search, custom shortcuts or a scripting API from.
- Tools (Select, Node, drawing tools) are Qt-free state machines but live in `views/`.

This spec restructures veccy into **document + operations + tools**: a *session* owns state, undo history and change notification; *operations* are the only code that edits state, registered with metadata; *tools* turn input into operations; *views* are Qt only. It is a restructuring: **no user-visible behavior changes** except undo/redo menu entries naming the edit they undo.

## Alignment with Product Vision

- **Professional depth, approachable surface (principle 2)** and **Customization** (customizable shortcuts, command search) need one registry of commands with labels and enabled checks.
- **Extensibility** (plugin/scripting API, potential enhancement): operations as plain, registered functions are the natural scripting surface.
- **Reliability: every edit undoable** stays guaranteed by routing all edits through the session's history; command-based undo (tech.md "undo scaling" limitation) becomes a change inside the session, not across the code base.
- **Keep the architecture clean and the codebase approachable so the project can grow and accept contributors** (business objective): package names that say what they hold, a dependency direction that the code actually follows, small focused modules, readable names.

## Requirements

### Requirement 1 — Layered packages with one dependency direction

**User Story:** As a contributor, I want each package to hold one kind of code and to import only from the layers below it, so that I can find code by its job and change one layer without surprises in another.

#### Acceptance Criteria

1. WHEN the restructuring is complete THEN the package layout SHALL be: `models/` (plain data), `geometry/` (pure shape math), `formats/` (file formats), `render/` (Skia drawing and picking), `editing/` (session and operations), `tools/` (Qt-free input state machines), `views/` (Qt widgets only), plus `app.py` and `icons.py`.
2. WHEN a module imports another veccy module THEN it SHALL follow `models ← geometry ← render ← editing ← tools ← views`, with `formats` importing only `models` and `geometry`, and `editing` allowed to use `formats` and `render` (export, text outlines).
3. WHEN `geometry/`, `formats/`, `render/`, `editing/` or `tools/` are imported THEN they SHALL contain no Qt imports.
4. WHEN the restructuring is complete THEN `controllers/` SHALL no longer exist; `geometry.py`, `affine.py` and `nodes.py` live in `geometry/`, `svg_io.py` becomes `formats/svg.py`.
5. WHEN the dependency rule is checked THEN a pytest test SHALL scan imports and fail on any import that goes against the direction or brings Qt into a Qt-free package.

### Requirement 2 — Session: state, undo history and change notification

**User Story:** As a contributor, I want one small object that owns the state, the undo history and change notification, so that every edit gets undo and refresh the same way and later undo or notification changes stay in one place.

#### Acceptance Criteria

1. WHEN the app starts THEN `App` SHALL create one `Session` holding the `AppState`, the undo/redo history and the subscriber list, and pass it explicitly to tools and views (no module-level state).
2. WHEN an operation edits the document THEN it SHALL do so inside a session edit scope that records one undo step with a human-readable label (e.g. "Move 3 objects", "Delete node") before mutating, and notifies subscribers once when the scope ends.
3. WHEN consecutive edits share a merge key (spinbox steps, rotation field) THEN they SHALL form one undo step, as today.
4. WHEN an operation changes non-document state (selection, active tool, zoom, node selection, tool styles) THEN it SHALL notify subscribers without recording undo, as today.
5. WHEN the user opens the Edit menu THEN Undo and Redo SHALL show the label of the step they would undo/redo (e.g. "Undo Move 3 objects"), and be disabled with plain "Undo"/"Redo" when there is none.
6. WHEN undo/redo runs THEN selection pruning, node-selection clearing and the dirty flag SHALL behave as today.

### Requirement 3 — Operations: the only code that edits state

**User Story:** As a contributor, I want every edit to be a named, plain function in a feature module, so that I can read, test and call edits without going through a large class.

#### Acceptance Criteria

1. WHEN state is changed by the app THEN the change SHALL go through a function in `editing/operations/`; views and tools SHALL NOT assign to `AppState` or call session internals directly.
2. WHEN operations are organized THEN they SHALL live in feature modules (e.g. `selection`, `shapes` (creation), `transform`, `nodes`, `style`, `layers`, `documents`, `view` (tool/zoom)), each well under ~400 lines.
3. WHEN an operation needs user input (paths, text, numbers, points) THEN it SHALL take plain values as parameters; dialogs stay in views.
4. WHEN an operation can run from a menu, toolbar or shortcut without extra input THEN it SHALL be registered with a stable id (e.g. `edit.delete`, `path.object_to_path`), a label and an optional "can run now?" check.
5. WHEN registered operations are listed THEN the registry SHALL return them in a stable order with id, label, enabled check and callable, independent of Qt.
6. WHEN an operation is called while its check says it can't run THEN it SHALL do nothing and leave state and history unchanged.
7. WHEN operations are tested THEN pytest SHALL cover them headless; the existing controller tests SHALL be moved to the matching operation test modules with the same assertions.

### Requirement 4 — Tools package

**User Story:** As a contributor, I want each tool to be its own Qt-free module with a common interface, so that adding a tool means adding one module.

#### Acceptance Criteria

1. WHEN the restructuring is complete THEN `tools/` SHALL contain one module per tool or tool family (`select.py`, `node.py`, `pen.py`, `shapes.py` (rectangle/ellipse), `text.py`) plus shared types (modifiers, cursor types, tool context).
2. WHEN a tool is used THEN it SHALL implement one common interface: press, move, release, double-click, hover (cursor type), escape, cancel, overlay and hint.
3. WHEN a tool commits a gesture THEN it SHALL call operations, never mutate state.
4. WHEN tools are listed for the tool strip and Tools menu THEN they SHALL come from a tool registry (id, label, `Tool` enum value), and `CanvasView` SHALL dispatch input to the active tool through it.
5. WHEN the restructuring is complete THEN `views/` SHALL no longer contain gesture logic; `canvas_view.py` forwards Qt events to the active tool.

### Requirement 5 — Views built from the registries

**User Story:** As a contributor, I want menus, toolbars and shortcuts built from the operation and tool registries, so that a new command needs no hand-written QAction wiring and shortcuts live in one keymap.

#### Acceptance Criteria

1. WHEN the main window is built THEN QActions for registered operations and tools SHALL be created from the registries; enabled state SHALL come from each operation's check on every refresh.
2. WHEN shortcuts and icons are assigned THEN they SHALL come from one keymap module in `views/` (operation/tool id → shortcut, icon), separate from the operations (as in Blender's keymaps), so that customizable shortcuts can later replace it.
3. WHEN commands need dialogs (open, save as, export PNG, add text, fit to window, about, quit) THEN they SHALL stay window commands in views that call operations with plain values.
4. WHEN menus and toolbars are shown THEN their content, order, labels, shortcuts, icons and tooltips SHALL match today's (except the undo/redo labels from Requirement 2.5).

### Requirement 6 — No behavior or performance change

**User Story:** As an artist, I want veccy to work exactly as before after the restructuring, so that nothing I rely on breaks.

#### Acceptance Criteria

1. WHEN the restructuring is complete THEN all existing pytest tests SHALL pass, moved and updated for the new imports and names only; assertions SHALL keep their meaning.
2. WHEN the app is driven through the existing interaction checks (select, move, scale, rotate, node edit, object to path, delete, undo, layers, open/save/export) offscreen and on the desktop GL renderer THEN behavior SHALL match the previous version.
3. WHEN `scripts/bench_canvas.py` runs THEN frame times and hover time SHALL be within noise of the previous version.
4. WHEN SVG files are saved and opened THEN output and results SHALL be identical to before.

### Requirement 7 — Documentation and naming

**User Story:** As a contributor, I want the docs to describe the architecture veccy really has, in its own words, so that I learn it once and correctly.

#### Acceptance Criteria

1. WHEN the restructuring is complete THEN CLAUDE.md, `structure.md` and `tech.md` SHALL describe the session / operations / tools / views architecture, the package layout and the dependency rule, and SHALL no longer call it MVC.
2. WHEN code is moved or rewritten in this spec THEN names SHALL be speaking but not overlong (`session`, `shape`, `segments`, `frame` rather than `c`, `s`, `sp`, `g`; short names stay fine for math and tiny scopes), and SHALL use "type" rather than "kind".
3. WHEN the restructuring is complete THEN no app module SHALL exceed ~400 lines.

## Non-Functional Requirements

### Code Architecture and Modularity
- Operations are plain functions with a small registration decorator; no class per command.
- The session stays small (state, history, notify, edit scope) and has no feature logic.
- Registries are plain Python data, Qt-free and testable.

### Performance
- No extra work per mouse move or frame: tools keep the current preview paths (matrix replay, live shapes); notification stays one refresh per committed edit.

### Reliability
- The move happens in small steps that each keep the full test suite green, so a regression is caught at the step that caused it.
- Undo history, dirty flag, selection pruning and SVG output are byte-for-byte or behavior-identical to before.

### Usability
- Only visible change: Undo/Redo menu entries name the step (e.g. "Undo Rotate"), which also helps users understand what Ctrl+Z will do.
