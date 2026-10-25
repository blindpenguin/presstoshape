# Requirements Document

## Introduction

**Live corners** round, invert or chamfer any corner node of a path without destroying it, the way Illustrator's corner widgets work. In the Node tool, each corner gets a small **corner widget** (a dot just inside the corner); dragging it rounds the corner, and every selected corner follows. The path remembers the radius per node: its nodes stay where they were, the drawn outline is rounded, and the radius can be changed or removed at any time.

This covers FEATURE_GAPS.md P2 "Corner rounding on any path node (live corners)" and is the non-destructive counterpart of the Corner command added in spec `path-structure`.

## Alignment with Product Vision

- **Principle 3, Non-destructive by default**: the rounding stays editable; the original corner is never lost.
- **Principle 1, Artists first**: one drag on the canvas, no dialog needed; the dialog is there for exact values.
- **Target users "People leaving Illustrator"**: same gesture and the same three corner kinds.
- **Principle 4, Own format for fidelity, SVG for exchange**: `.p2s` keeps the live corners; SVG gets the rounded outline that every program shows, with the live data in PressToShape metadata (the Composite approach).
- **Principle 6, What you see is what you export**: canvas, PNG and SVG show the same rounded outline.

## Requirements

### Requirement 1: Corner data on paths

**User Story:** As a designer, I want a path to remember how each corner is rounded, so that I can change the rounding later instead of redrawing.

#### Acceptance Criteria

1. Each node of a path SHALL be able to carry a **corner radius** (≥ 0, in document pixels) and a **corner kind**: `round`, `inverted` (a concave quarter circle cut into the corner) or `chamfer` (a straight cut). A radius of 0 means a sharp corner.
2. Only **corner nodes** with a segment on both sides SHALL be drawn rounded. A smooth node or an end node of an open subpath is drawn as it is, whatever it stores; the commands that make a node smooth or an end node clear its radius (Requirement 5.3).
3. The node positions and handles SHALL stay exactly as they are; only the drawn outline changes.
4. The rounding SHALL work next to straight and curved segments.
5. The radius SHALL be limited when drawing so that roundings never overlap: the cut on each segment can use at most the part of the segment that the neighbouring corner leaves free (half the segment when both ends are rounded). A radius larger than fits SHALL be drawn at the largest fitting size and SHALL keep its stored value.

### Requirement 2: Drawing and using the rounded outline

**User Story:** As a user, I want the rounded corners to behave like real geometry everywhere, so that what I see is what I get.

#### Acceptance Criteria

1. The canvas, PNG export, hit-testing, bounds (selection frame, align, distribute), booleans, divide, Composite parts and clip/mask objects SHALL use the rounded outline.
2. Snapping SHALL keep offering the path's nodes (as today); edge, centre and bounds targets SHALL use the rounded outline.
3. Stroke dashes SHALL run along the rounded outline.
4. Drawing cost SHALL not grow for paths without rounded corners, and the rounded outline SHALL be computed once per path change (cached like other geometry).

### Requirement 3: Corner widgets in the Node tool

**User Story:** As an illustrator, I want to drag a dot inside a corner to round it, so that I can shape corners directly on the canvas.

#### Acceptance Criteria

1. WHEN the Node tool edits a path THEN a corner widget SHALL be shown for each roundable corner node that is selected; with no node of that path selected, for every roundable corner node of the path.
2. The widget SHALL sit on the corner's bisector, inside the angle, a fixed screen distance from the node, or at the start of the rounded arc when the corner is already rounded further than that.
3. Widgets SHALL be hidden when the corner is too small to show them clearly (for example the adjacent segments are shorter than a few screen pixels), and SHALL be hidden while nodes or handles are being dragged.
4. WHEN the user drags a widget THEN the radius of that corner SHALL follow the pointer (distance along the bisector), with a live preview; IF other corner nodes are selected THEN all selected roundable corners SHALL get the same radius. Release commits one undo step ("Round corners").
5. WHILE dragging, the outline SHALL show where the radius had to be limited (for example the affected corners' arcs drawn in a warning colour), like Illustrator's red highlight.
6. Dragging the widget back into the node SHALL set the radius to 0.
7. Widgets SHALL take priority over the path's segments for clicks, but nodes and handles SHALL take priority over widgets.
8. The cursor SHALL show that a widget can be dragged.

### Requirement 4: Exact values and kinds

**User Story:** As a designer, I want to type an exact radius and choose round, inverted or chamfer, so that I can match a design specification.

#### Acceptance Criteria

1. WHEN the user double-clicks a widget THEN a small dialog SHALL open with kind (round, inverted, chamfer) and radius (in the document unit), applying to the selected roundable corners (or that one corner if it isn't selected). OK applies as one undo step.
2. The Node tool's options SHALL show a **Corner** row with kind and radius for the selected corner nodes (mixed values shown as empty/mixed), editable directly; spinbox steps merge into one undo step.
3. A menu command **Path → Selected Nodes → Remove Corner Rounding** SHALL set the radius of the selected nodes (or all nodes of the selected paths) to 0.

### Requirement 5: Editing paths with live corners

**User Story:** As a user, I want live corners to survive normal editing, so that I don't lose them by moving a node.

#### Acceptance Criteria

1. Moving nodes and handles, nudging, transforms (move, rotate, flip, scale) SHALL keep the radii. Scaling SHALL NOT scale the radii (as rectangle corner radii today); importing SVG transforms is not affected (radii come from metadata in path units, see Requirement 6).
2. Inserting a node SHALL give the new node no rounding; deleting a node SHALL drop its rounding.
3. The structure commands of spec `path-structure` SHALL keep the radius of every node they keep: break and join make new end/merged nodes without rounding; Smooth and Symmetric clear the radius of the nodes they change; Corner keeps it; Reverse, Close/Open, Combine/Split keep it per node.
4. **Path → Apply Corner Rounding** SHALL bake the rounded outline into real nodes (radius 0 afterwards), one undo step. Object to Path on a path with live corners SHALL do the same.
5. Booleans, divide and Flatten Composite produce new paths from the rounded outline (no live corners on the result).

### Requirement 6: Files and clipboard

**User Story:** As a user, I want live corners kept in my files and readable by other programs, so that nothing is lost on save.

#### Acceptance Criteria

1. `.p2s` SHALL store radius and kind per node (only for nodes with a radius); format version bump, migration, sample and `docs/file-format.md` row as the file-format rule requires.
2. SVG SHALL write the rounded outline as the path's `d`, so other programs show the same shape; the original segments and the per-node corners SHALL be stored in PressToShape metadata on the element (like Composites).
3. WHEN such a file is opened THEN the live corners SHALL come back, unless another program changed the path in the meantime (the stored outline no longer matches `d`): then the path SHALL open as a plain path with the visible outline, and no note is needed.
4. Copy/paste inside PressToShape SHALL keep live corners; pasting to other programs gives the rounded outline.
5. Saved SVG SHALL render the same in resvg as on the canvas (generator check).

## Non-Functional Requirements

### Code Architecture and Modularity
- The rounding geometry (cut lengths, arcs for round / inverted / chamfer on line and curve segments, limiting) is a pure module in `geometry/`, unit-tested on its own, and reused by `transforms.outline` and the Node tool preview.
- Widget placement and hit-testing are Qt-free (`render/handles.py` or a sibling); the gesture lives in `tools/node.py` and commits through one operation call.
- The dialog lives in `views/`; operations take plain values.

### Performance
- No extra per-frame cost for paths without live corners; for paths with them the rounded outline is cached per shape change. Dragging a widget re-rounds only the edited path.

### Reliability
- Every path that can be saved opens again unchanged (`.p2s` and SVG round trips tested).
- Degenerate input (zero-length segments, 180° corners, coincident handles) never raises; such corners stay sharp.

### Usability
- All texts translated (German); no new keyboard shortcuts.
- **Out of scope**: live corners on rectangles converted to paths (Object to Path keeps baking them), corner widgets in the Select tool, per-corner "relative/absolute" rounding modes, scaling radii with a preference.
