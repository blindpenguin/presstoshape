# Requirements Document

## Introduction

The **Pen tool** becomes a proper bezier pen, working the way artists know from Illustrator, Affinity Designer and Inkscape. Today every click adds a point of a Catmull-Rom spline: all segments are curves, their shape is decided by the neighbouring points rather than by the user, and paths can't be closed.

After this spec:

- a **click** places a corner node, and the segment to it is a **straight line**;
- **click + drag** places a smooth node and pulls out its bezier handles, so the segment **curves**;
- clicking the **first node** closes the path;
- a live preview shows what the next click will create.

The result is an ordinary path whose nodes and handles are exactly the ones placed, so the Node tool shows the same structure the user drew.

## Alignment with Product Vision

- **Product pillar 5, Path editing & construction**: precise path construction is the base of logo, icon and illustration work, and the pen is its main tool.
- **Principle 1, Artists first**: the pen follows the standard gesture vocabulary (click = corner, drag = curve, click the start = close), so users coming from other editors don't have to relearn it.
- **Target users "People leaving Illustrator"**: "familiar concepts and workflows".
- **Principle 2, Professional depth, approachable surface**: the basic gesture is just click and drag; modifiers add control without being needed.

## Requirements

### Requirement 1: Straight segments by clicking

**User Story:** As a designer, I want each click to add a corner point joined by a straight line, so that I can draw polygons and precise outlines quickly.

#### Acceptance Criteria

1. WHEN the user clicks on the canvas with the Pen tool and no path is in progress THEN a new path SHALL start with a corner node at that point.
2. WHEN the user clicks (press and release without dragging beyond a few screen pixels) while a path is in progress THEN a corner node SHALL be added, and the segment from the previous node SHALL be a straight line if the previous node has no outgoing handle.
3. IF the previous node is a smooth node (has an outgoing handle) THEN the new segment SHALL be a curve that leaves the previous node along that handle and arrives at the new corner node without an incoming handle.
4. Straight segments SHALL be stored as line segments (not as cubics with collapsed handles), so the Node tool, SVG output and `.p2s` see plain lines.
5. WHEN Shift is held while clicking THEN the new node SHALL be placed so the segment from the previous node is constrained to multiples of 45°.
6. Node positions SHALL snap like other drawing tools (grid, guides, other shapes' points, the path's own existing nodes); Ctrl ignores snapping.

### Requirement 2: Curved segments by click + drag

**User Story:** As an illustrator, I want to drag out handles while placing a point, so that I can shape smooth curves directly as I draw.

#### Acceptance Criteria

1. WHEN the user presses and drags beyond a few screen pixels THEN the node SHALL be placed at the press point and the drag SHALL pull out its **outgoing** handle to the pointer; the **incoming** handle SHALL mirror it (same length, opposite direction), making a smooth symmetric node.
2. While dragging, the segment arriving at the node SHALL be previewed live with the handles shown.
3. WHEN the very first node of a path is dragged THEN only the outgoing handle SHALL matter (there is no incoming segment).
4. WHEN Shift is held while dragging THEN the handle direction SHALL be constrained to multiples of 45°.
5. WHEN Alt is held while dragging THEN only the outgoing handle SHALL follow the pointer and the incoming handle SHALL stay where it was, giving a cusp node (the curve can change direction sharply there). Releasing Alt during the drag SHALL make the handles mirror again.
6. Handle end points SHALL NOT snap (only node positions snap), so curve shaping stays fluid.
7. The resulting node SHALL be reported as smooth by the Node tool when the handles are mirrored, and as a corner when they were broken with Alt.

### Requirement 3: Closing paths

**User Story:** As a designer, I want to close a path by clicking its starting point, so that I can draw filled shapes with the pen.

#### Acceptance Criteria

1. WHEN a path in progress has at least two nodes AND the pointer hovers within a few screen pixels of the first node THEN the canvas SHALL show that a click will close the path (distinct cursor and a highlighted first node), and the preview SHALL show the closing segment.
2. WHEN the user clicks the first node in that state THEN the path SHALL be closed and committed: the closing segment follows the same rules as any other (straight if neither end has a handle on that side, a curve otherwise).
3. WHEN the user presses on the first node and drags THEN the drag SHALL shape the first node's handles (mirrored, Alt breaks them as in Requirement 2), so the closing curve can be shaped, and releasing SHALL close and commit the path.
4. A closed path SHALL be stored as a closed subpath (ending with close-path) with no duplicate node at the start, so the Node tool shows the first node once and fill renders correctly.
5. Hovering the first node SHALL take priority over snapping to other targets.

### Requirement 4: Finishing, cancelling and correcting

**User Story:** As a user, I want clear ways to end, abandon or fix the path I'm drawing, so that a mistake doesn't force me to start over.

#### Acceptance Criteria

1. WHEN the user presses Enter or double-clicks THEN the path SHALL be committed as an **open** path (if it has at least two nodes); a double-click SHALL NOT add an extra node.
2. WHEN the user presses Esc THEN the path in progress SHALL be discarded and nothing created.
3. WHEN the user presses Backspace (or Delete) while a path is in progress THEN the last placed node SHALL be removed; removing the only node ends the path in progress without creating anything.
4. WHEN the user switches to another tool while a path with at least two nodes is in progress THEN that path SHALL be committed as an open path instead of being lost.
5. A committed path SHALL be added and selected as one undo step ("Add path"), in the Pen's style, like other new shapes:
   - to the active layer;
   - inside an entered group or Composite, there (as a part in the new-part mode);
   - IF the active layer is hidden, with the existing "Layer is hidden" message.
6. A path with fewer than two distinct nodes SHALL NOT be created.

### Requirement 5: Feedback while drawing

**User Story:** As a user, I want to see what my next click will do, so that I can draw precisely without trial and error.

#### Acceptance Criteria

1. While a path is in progress THEN the canvas SHALL show the committed part of the path in the Pen's stroke style, its nodes, the handles of the last node, and a **rubber-band** segment from the last node to the pointer (straight, or curved if the last node has an outgoing handle).
2. The preview SHALL be visible even when the Pen's style has no stroke (a thin helper outline in the canvas overlay colour).
3. Snap hits SHALL be shown with the existing snap feedback.
4. Cursors SHALL tell apart: starting a new path, adding a node, and closing the path (Requirement 3.1).
5. The tool options hint SHALL describe the gestures: click for corners, drag for curves, click the first node to close, Enter / double-click to finish, Backspace to remove the last node, Esc to cancel; Shift and Alt modifiers.

## Non-Functional Requirements

### Code Architecture and Modularity
- The gesture state machine stays in `tools/pen.py` (Qt-free, a `BaseTool` subclass) and commits through one operation call.
- Building segments from pen nodes (corner/smooth node with optional in/out handles, open or closed) is pure geometry in `geometry/`, unit-tested on its own.
- New cursor types are `CursorType` values mapped only in `views/cursors.py`.
- Existing callers of `shapes.add_path(session, points)` (demo shapes, tests) keep working or are moved to the new representation in the same change.

### Performance
- Per-move cost stays small: the preview only rebuilds the in-progress path and rubber band, never the document picture.

### Reliability
- Paths drawn with the pen round-trip through `.p2s` and SVG unchanged (no file format change is expected: only line, cubic and close segments are produced).
- Fully tested with `ToolDriver` in `tests/tools/test_pen.py`: click-only polygons, drag curves, mixed segments, Shift/Alt modifiers, closing by click and by drag, Enter/double-click/Esc/Backspace, tool switch, snapping.

### Usability
- Shortcut `P` and icon stay. Hint text updated, German translation complete.
- **Out of scope** (later specs):
  - continuing or joining an existing open path from its end node;
  - adding nodes to or deleting nodes from an existing path with the Pen (the Node tool does that);
  - Space while dragging to reposition the node being placed;
  - converting a node's type with the Pen (Alt-click on a node in Illustrator);
  - rubber-band preview toggle and other pen preferences.
