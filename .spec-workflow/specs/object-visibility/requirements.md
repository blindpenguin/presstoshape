# Requirements Document

## Introduction

Today only whole layers can be hidden, and nothing can be locked. Artists constantly need both for single objects: hide a shape that's in the way while working on what's under it, lock a background or a traced sketch so stray clicks and rubber bands don't grab it. Every common editor offers this (Illustrator Object → Hide / Lock, Inkscape's Objects dialog, Affinity's Layers panel).

This spec adds:

- **Hide** and **lock** for individual objects (any shape, group, group child or Composite part), with Object menu commands and shortcuts: Hide Selection, Show All, Lock Selection, Unlock All.
- **Lock for layers**, next to the existing layer visibility.
- An **object tree in the Layers panel**: objects listed under their layer, groups and Composites expandable, an eye and a lock toggle on every row, and selection kept in sync with the canvas. It is the only way to bring back or unlock one particular object, since hidden and locked objects can't be clicked on the canvas.

Both states are saved in `.p2s` and SVG (`display:none` and Inkscape's `sodipodi:insensitive`), so they survive a round trip with Inkscape.

## Alignment with Product Vision

- **Feature gap list, P1 "Editing"**: "Lock and hide individual objects, not only layers." Part of the P2 item "Layers panel upgrade" (object tree, lock layers) comes along because it is the natural place to toggle both.
- **Principle 1, Artists first**: locking a sketch or background and hiding clutter are everyday drawing-flow actions.
- **Principle 5, Inkscape interop**: Inkscape stores both states in SVG; files keep them both ways.
- **Target users, people leaving Illustrator**: familiar commands and shortcuts (Ctrl+2 / Ctrl+3 family).

## Requirements

### Requirement 1: Hide objects

**User Story:** As an artist, I want to hide individual objects, so that I can work on what's behind them without deleting or moving them.

#### Acceptance Criteria

1. WHEN one or more objects are selected AND the user runs Object → Hide Selection (Ctrl+3) THEN the system SHALL hide them and clear the selection. One undo step, "Hide".
2. A hidden object SHALL NOT be drawn on the canvas or in PNG export, SHALL NOT be hit by clicks or rubber bands, SHALL NOT be a snapping target, and SHALL NOT count for Select All, align/distribute to the artboard or anything else that looks at "visible shapes".
3. WHEN the user runs Object → Show All (Ctrl+Alt+3) THEN every hidden object in the document (inside groups and Composites too) SHALL be shown again, and those of them that are selectable right now (in the active container, not locked) SHALL become the selection. One undo step, "Show all". Show All SHALL be disabled when nothing is hidden. Layer visibility SHALL NOT change.
4. WHEN a group is hidden THEN everything in it SHALL be hidden with it, without changing the children's own states; showing the group shows the children that were not hidden themselves.
5. WHEN a Composite part is hidden THEN it SHALL be left out of the Composite's result (as if removed), and the result SHALL update. A Composite whose parts are all hidden draws nothing.
6. WHEN a hidden object is inside a selected group that is moved, scaled, rotated, flipped, restyled, copied, duplicated or deleted THEN the hidden object SHALL be treated like the group's other children (it moves with the group and stays hidden).
7. WHEN the entered group or Composite (edit mode) is hidden THEN edit mode SHALL leave it.
8. Hide Selection SHALL be disabled with nothing selected.

### Requirement 2: Lock objects

**User Story:** As an artist, I want to lock objects, so that I can draw over a sketch or background without grabbing it by accident.

#### Acceptance Criteria

1. WHEN one or more objects are selected AND the user runs Object → Lock Selection (Ctrl+2) THEN the system SHALL lock them and clear the selection. One undo step, "Lock".
2. A locked object SHALL stay drawn, exported and a snapping target, but SHALL NOT be selectable by click, rubber band, Select All, the Node tool or double-click to enter; a click on it SHALL act on whatever selectable object lies below, or on empty canvas.
3. WHEN the user runs Object → Unlock All (Ctrl+Alt+2) THEN every locked object in the document SHALL be unlocked, and those of them that are selectable right now SHALL become the selection. One undo step, "Unlock all". Unlock All SHALL be disabled when nothing is locked. Layer locks SHALL NOT change.
4. WHEN a group is locked THEN nothing in it SHALL be selectable and it SHALL NOT be enterable; the children's own states stay.
5. WHEN a locked object is inside a selected group THEN group-wide actions (move, scale, rotate, flip, restyle, copy, delete) SHALL include it, as Inkscape and Illustrator do. A lock protects against picking, not against the container it belongs to.
6. WHEN the entered group or Composite is locked THEN edit mode SHALL leave it.
7. Lock Selection SHALL be disabled with nothing selected.

### Requirement 3: Lock layers

**User Story:** As an artist, I want to lock a whole layer, so that I can protect a reference or background layer in one click.

#### Acceptance Criteria

1. Each layer SHALL have a lock state, toggled from the Layers panel. One undo step, "Lock layer" / "Unlock layer".
2. Shapes in a locked layer SHALL behave as locked objects (Requirement 2.2) while the layer is locked, without changing their own state.
3. WHEN the active layer is locked THEN drawing a new shape SHALL be refused with a status message ("Layer '{name}' is locked"), as for a hidden layer today; pasting SHALL behave as on a hidden layer today (pasted, with a note).
4. WHEN the layer of the entered container gets locked or hidden THEN edit mode SHALL leave.

### Requirement 4: Object tree in the Layers panel

**User Story:** As a designer, I want to see the objects of each layer in a list with eye and lock toggles, so that I can find, show, unlock and select any particular object, including ones I can't click on the canvas.

#### Acceptance Criteria

1. The Layers panel SHALL show a tree: layers topmost first, each layer's objects under it topmost first, and the children of groups and parts of Composites under them. Layers start expanded, groups and Composites collapsed.
2. Each row SHALL show an icon for the object's type and a label: the type name ("Rectangle", "Ellipse", "Path", "Group", "Composite") or, for text, its text (shortened). Object naming is out of scope.
3. Each row (layers and objects) SHALL have an eye toggle and a lock toggle. Toggling SHALL hide/show or lock/unlock that one row's object or layer, one undo step each, and SHALL NOT change the selection otherwise.
4. Rows of objects that are effectively hidden or locked by an ancestor (layer, group, Composite) but not themselves SHALL show the toggle dimmed, so it's clear why they can't be seen or picked.
5. WHEN the user clicks an object row THEN that object SHALL become the selection, entering the containers around it if it's inside a group or Composite (as double-clicking into them would); Ctrl+click and Shift+click SHALL add to / extend the selection among rows of the same container. Clicking a hidden or locked row SHALL select the row only in the tree, not the object.
6. WHEN the selection changes on the canvas THEN the selected objects' rows SHALL be highlighted and the tree SHALL expand and scroll to show the first of them.
7. Clicking a layer row SHALL make it the active layer, as today; double-click on a layer renames it, as today. Add and delete layer buttons stay.
8. Drag-and-drop reordering, nested layers, layer opacity and object names are out of scope (they remain in the "Layers panel upgrade" gap item).

### Requirement 5: Files and clipboard

**User Story:** As a user, I want hidden and locked states to survive saving, reopening, copying, undo and a round trip through Inkscape.

#### Acceptance Criteria

1. `.p2s` SHALL store the hidden and locked state of every object and the locked state of layers, in a new format version with a migration from the previous one (old files open with everything shown and unlocked), a sample file and a `docs/file-format.md` row.
2. WHEN saved as SVG THEN a hidden object SHALL be written with `style="display:none"`, a locked object or layer with `sodipodi:insensitive="true"`; the clipboard SVG likewise.
3. WHEN an SVG is opened or pasted THEN shapes and groups with `display:none` SHALL be imported as hidden objects (today they are dropped), and elements with `sodipodi:insensitive="true"` as locked objects or layers. `display:none` inside `<symbol>`/`<defs>` content and other non-rendered elements keep today's handling.
4. Copy and paste inside PressToShape SHALL keep the states of objects inside copied groups and Composites. Pasted top-level objects SHALL arrive shown and unlocked (they were selected, so they were neither).
5. Every hide/show/lock/unlock SHALL be undoable; undo snapshots stay cheap (shared frozen shapes).

### Requirement 6: Commands and shortcuts

**User Story:** As someone coming from Illustrator, I want the familiar commands and keys.

#### Acceptance Criteria

1. The Object menu SHALL have Hide Selection (Ctrl+3), Show All (Ctrl+Alt+3), Lock Selection (Ctrl+2) and Unlock All (Ctrl+Alt+2), registered as operations with ids, menu labels and `can_run`.
2. The commands SHALL work in edit mode on the selection inside the entered container.
3. Status bar messages SHALL say what happened ("{count} objects hidden", "Nothing to show").

## Non-Functional Requirements

### Code Architecture and Modularity
- Hidden and locked states live in the frozen shape data (every shape type, groups included) and on `Layer`; changes go through `dataclasses.replace` and `change_container`.
- One place decides what is visible and what is pickable (`editing/containers.py` / `editing/queries.py` and `render/scene.visible_shapes`), so tools, snapping, hit-testing and commands don't each re-implement the rules.
- Operations in `editing/operations/visibility.py`; shortcuts in `views/keymap.py`; the tree in its own view module(s), Qt-free logic (row model, effective states) testable below `views/`.

### Performance
- Canvas frame cost and `scripts/bench_canvas.py` numbers SHALL stay the same for documents with nothing hidden; hidden objects cost nothing per frame.
- The object tree SHALL stay responsive with 10,000 shapes: opening such a file, selecting on the canvas and dragging shapes SHALL not cause noticeable delays from the panel (no full rebuild on every refresh; collapsed branches not built).

### Reliability
- Everything the app can save opens again (round-trip tests for hidden/locked shapes, group children, Composite parts and layers in `.p2s` and SVG).
- Malformed `sodipodi:insensitive` values in foreign SVG are ignored, never a crash.

### Usability
- Familiar Illustrator shortcuts; eye and lock icons as in Inkscape, Illustrator and Affinity (Tabler icons).
- All new UI text in British English source with German translations.
- Hidden or locked state is never invisible to the user: the tree always shows it, and Show All / Unlock All are one keystroke away.
