# Requirements Document

## Introduction

Designers place things precisely: logos centred on the artboard, icons on a pixel grid, buttons lined up and evenly spaced. PressToShape has no tools for that yet. This spec adds the precision basics every vector editor has:

- **Align and distribute** selected objects to each other or to the artboard.
- **Rulers** along the canvas, in the document's unit.
- **Guides** dragged out of the rulers.
- **Grid** with adjustable spacing.
- **Snapping** while moving, scaling and drawing: to the grid, guides, the artboard, other objects' edges and centres (including alignment lines across a distance, "smart guides"), and path nodes, with visual feedback showing what was snapped to.

## Alignment with Product Vision

- **Pillar 6, Precision & layout**: "transforms with handles, snapping, grids, guides, align/distribute, artboards". This spec delivers everything in it except artboards.
- **Target users**: graphic and UI designers need "alignment, snapping, export"; people leaving Illustrator expect these from day one.
- **Feature gap list, P1 "Layout and precision"** (align and distribute; snapping; rulers, guides, grid) and step 2 of the suggested order.
- **Principle 1, Artists first**: snapping must never fight the hand: easy to switch off, temporarily ignored with one key, and fast enough not to lag.
- **Principle 5, Inkscape interop**: guides and the grid travel through SVG in Inkscape's own format.

## Requirements

### Requirement 1: Align

**User Story:** As a designer, I want to line up objects along an edge or their centres, so that layouts look tidy without measuring.

#### Acceptance Criteria

1. Object → Align SHALL offer: Left, Centre Horizontally, Right, Top, Centre Vertically, Bottom.
2. The same commands SHALL be available in a new **Align** panel in the right sidebar, below the Layers panel: a row of icon buttons with tooltips, and a "Relative to" choice: **Selection** (the bounds of all selected objects, default) or **Artboard**. The panel is always visible; its buttons are disabled when the command can't run (nothing selected, or too few objects to distribute). It is the place for later arrangement tools too (e.g. a Transform panel).
3. WHEN several objects are aligned relative to the selection THEN each SHALL move (not resize) so that its edge or centre lines up with the selection's; WHEN a single object is selected THEN it SHALL be aligned to the artboard whatever the choice says.
4. Alignment SHALL use the objects' geometric bounds (without stroke), the same box the selection frame shows. Groups and Composites move as one object.
5. Inside an entered group or Composite, the shapes inside SHALL be aligned (relative to the selection, or to the artboard).
6. Each align command SHALL be one undo step named after it ("Align left", …).

### Requirement 2: Distribute

**User Story:** As a designer, I want evenly spaced objects, so that rows and columns of items look regular.

#### Acceptance Criteria

1. Object → Distribute SHALL offer: Distribute Horizontally and Distribute Vertically (equal gaps between neighbouring objects), plus Distribute Centres Horizontally and Vertically (equal distance between centres).
2. WHEN three or more objects are selected THEN the outermost two (in that direction) SHALL stay where they are and the ones between SHALL move so the gaps (or centre distances) are equal, keeping their order along that axis; with fewer than three objects the commands SHALL be disabled.
3. Distribute buttons SHALL sit below the align buttons in the Align panel.
4. Each command SHALL be one undo step.

### Requirement 3: Rulers

**User Story:** As a designer, I want rulers along the canvas, so that I can see positions and sizes in my document's unit.

#### Acceptance Criteria

1. View → Show Rulers SHALL show a horizontal ruler above and a vertical ruler left of the canvas, on by default and remembered between sessions.
2. Rulers SHALL be labelled in the document's unit with zero at the artboard's top-left corner, and SHALL pick tick spacing so labels stay readable at every zoom (round steps such as 1, 2, 5, 10, …).
3. Rulers SHALL follow scrolling and zooming without lag and SHALL mark the pointer position; while objects are selected they SHALL also mark the selection's extent.
4. Rulers SHALL match the theme (light and dark).

### Requirement 4: Guides

**User Story:** As a designer, I want guides I can drag out of the rulers, so that I can line things up with positions I chose.

#### Acceptance Criteria

1. WHEN the user drags from the horizontal ruler onto the canvas THEN a horizontal guide SHALL follow the pointer and be placed on release (vertical ruler: vertical guide). Each placed guide is one undo step ("Add guide").
2. WHEN the user drags an existing guide (with the Select tool, when no object handle or object is under the pointer) THEN it SHALL move; dragging it back onto a ruler SHALL delete it. Moving and deleting are undo steps.
3. WHEN the user double-clicks a guide THEN a small dialog SHALL let them type its exact position in the document's unit, or delete it.
4. Guides SHALL be drawn as thin coloured lines across the whole canvas, above the drawing and below selection handles, one screen pixel wide at every zoom; the cursor SHALL show when a guide can be dragged.
5. View → Show Guides SHALL toggle their visibility (hidden guides don't snap); View → Lock Guides SHALL stop them from being moved by accident; View → Clear Guides SHALL remove all (one undo step).
6. Guides belong to the document: they SHALL be saved in `.p2s` and SVG (Inkscape's `sodipodi:guide` format, so Inkscape shows them and PressToShape reads Inkscape's guides), and they SHALL NOT appear in PNG export.
7. Angled guides are out of scope.

### Requirement 5: Grid

**User Story:** As an icon or UI designer, I want a grid to draw on, so that shapes land on regular positions.

#### Acceptance Criteria

1. View → Show Grid SHALL toggle a rectangular grid over the artboard area and the pasteboard, drawn below the shapes or above them faintly so it stays visible on filled areas, never in export.
2. The grid SHALL have a **spacing** (in the document's unit) and **major lines every N** lines; major lines are drawn stronger. Defaults depend on the unit (e.g. 10 px with major every 10, 5 mm with major every 2, ¼ in).
3. View → Grid Settings… SHALL open a small dialog to change spacing and major-line interval, as one undo step; grid settings belong to the document and SHALL be saved in `.p2s` and SVG (Inkscape's `inkscape:grid`).
4. WHEN lines would be closer than a few screen pixels at the current zoom THEN minor lines SHALL be hidden (and major lines if those are too close too), so the canvas never turns grey with lines.
5. Whether the grid is shown SHALL be a view setting saved with the document's working state, like zoom.

### Requirement 6: Snapping

**User Story:** As a designer, I want objects and points to jump to useful positions while I drag, so that I can be precise without zooming in.

#### Acceptance Criteria

1. Snapping SHALL be switched on and off globally with View → Snapping (and a magnet toggle button in the main toolbar), with a submenu View → Snap To with one checkbox per target: **Grid**, **Guides**, **Artboard** (edges and centre), **Objects** (other objects' bounding-box edges and centres, also when far away along the same line), **Nodes** (path nodes and the corners of rectangles). Snapping and the targets SHALL be remembered between sessions; defaults: snapping on, all targets on except Grid (it snaps when the grid is shown and Grid is checked).
2. WHEN moving objects with the Select tool THEN the selection's bounding-box edges and centre (and, with Nodes on, its nodes) SHALL snap to the nearest target within the snap distance, horizontally and vertically independently.
3. WHEN scaling with a handle THEN the dragged edge or corner SHALL snap; WHEN drawing a rectangle or ellipse, placing pen points or text THEN the pointer position SHALL snap; WHEN dragging path nodes with the Node tool THEN the dragged node SHALL snap (to everything except itself and its own path's moving nodes); WHEN dragging a guide THEN it SHALL snap to objects and nodes.
4. Pencil strokes, rotation, bezier handles and arrow-key nudges SHALL NOT snap.
5. The snap distance SHALL be measured in screen pixels (default 8), so it feels the same at every zoom, and SHALL be adjustable in Settings → Canvas.
6. Holding **Ctrl** during a drag SHALL ignore snapping for that moment.
7. WHILE a snap is active THEN the canvas SHALL show what was snapped to: a short label ("Grid", "Guide", "Node", "Edge", "Centre", "Artboard") at the snapped point, and for alignment to another object a thin line from the snapped edge or centre to that object.
8. Snapping SHALL stay fast: in a document with 10,000 shapes, a drag frame with snapping on SHALL not be noticeably slower than without it (target: under 2 ms of snapping work per frame), by preparing candidate positions when the gesture starts.

### Requirement 7: Shortcuts and menus

**User Story:** As a frequent user, I want the most used precision commands on keys, without the rarely used ones taking up combinations.

#### Acceptance Criteria

1. Snapping on/off SHALL have a shortcut: **%** (Inkscape's), reachable as Shift+5 on most layouts.
2. Show Rulers: **Ctrl+R**; Show Grid: **#** (Inkscape's); Show Guides: **|** (Inkscape's). Align and distribute commands, Lock/Clear Guides and Grid Settings SHALL have menu entries and panel buttons but no shortcuts.
3. All new texts SHALL be translated (English source, German), and menu mnemonics SHALL stay unique.

## Non-Functional Requirements

### Code Architecture and Modularity
- Align/distribute and snapping math are pure, Qt-free geometry (`geometry/align.py`, `geometry/snapping.py`), unit-tested.
- Guides and grid live in `models/` as document data (frozen where they are values); show/lock/snap toggles are view state in `AppState`, persisted by the views.
- Tools ask a snapping service from their context and stay Qt-free; rulers are Qt widgets in `views/`; guides and grid are drawn by `render/` with colours passed in.

### Performance
- Rulers, grid and guides SHALL add no measurable cost to `scripts/bench_canvas.py` frames when hidden, and stay within a frame budget when shown (grid lines drawn per frame only for the visible area).
- Snapping SHALL meet Requirement 6.8.

### Reliability
- `.p2s` gains a new format version with a migration; SVG guides and grid round-trip with Inkscape.
- Malformed guide or grid data in foreign SVG falls back to no guides / default grid with an import note.

### Usability
- Snapping feedback is quiet (thin lines, small labels) and never covers what is being moved.
- The right sidebar stacks Layers above Align; both share its height sensibly (Layers keeps most of it, Align takes only what its buttons need) and the split is remembered.
- Everything works in px, mm, cm, in and pt documents and at every zoom.
