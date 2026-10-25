# Requirements Document

## Introduction

Paths can be drawn (Pen, Pencil) and their nodes moved, inserted and deleted (Node tool), but their **structure** can't be changed: a path can't be opened, closed, cut at a node or joined to another, node types can't be set, and compound paths can only come from booleans. This spec adds the structural path editing that Inkscape, Illustrator and Affinity Designer all offer:

- **node types**: make the selected nodes corner, smooth or symmetric, and turn segments into lines or curves;
- **break and join**: cut a path at selected nodes, join two end nodes (of one path or of two paths), and delete a segment between two nodes;
- **open / close** subpaths and **reverse** path direction;
- **combine / split**: merge several paths into one compound path, and break a compound path into one path per subpath;
- **Pen continues paths**: start the Pen on an open path's end node to extend it, and finish on another end node to join.

It covers FEATURE_GAPS.md P2 "Join / break / cut paths, close path, combine and split compound paths", "Node tool extras: node types buttons" and "reverse direction", and the P1 Pen leftover "continuing or joining an existing path from its end".

## Alignment with Product Vision

- **Pillar 5, Path editing & construction**: these are the everyday path-surgery commands of every vector editor; without them a drawn path that's slightly wrong has to be redrawn.
- **Principle 1, Artists first**: continuing a path with the Pen and fixing node types right on the canvas keeps the drawing flow.
- **Principle 2, Professional depth, approachable surface**: the node commands appear in the Node tool's options panel only while the Node tool is active; the menu holds the rest.
- **Principle 5, Inkscape interop**: everything produced is ordinary path data (move, line, cubic, close), so SVG and Inkscape see plain paths.

## Requirements

### Requirement 1: Node types

**User Story:** As an illustrator, I want to set selected nodes to corner, smooth or symmetric, so that I can fix kinks and bumps without redrawing.

#### Acceptance Criteria

1. WHEN the Node tool is active THEN its options panel SHALL show buttons **Corner**, **Smooth**, **Symmetric**, **Make Line**, **Make Curve**, enabled only when the relevant nodes/segments are selected; the same commands SHALL be in the Path → Nodes menu.
2. WHEN **Smooth** is applied to a node with two handles THEN both handles SHALL be rotated onto one line through the node (each keeping its length), along the average of their directions.
3. WHEN **Smooth** is applied to a node that has a handle on only one side, or none, THEN handles SHALL be created along the direction between its neighbouring nodes, each a third of the distance to that neighbour; adjoining line segments become curves that keep their current shape as far as possible.
4. WHEN **Symmetric** is applied THEN the result SHALL be as for Smooth and the two handles SHALL also get the same length (the average of both).
5. WHEN **Corner** is applied THEN the node SHALL be marked so the Node tool no longer keeps its handles aligned while dragging one of them; handle positions SHALL NOT change.
6. WHEN **Make Line** is applied with two or more adjacent nodes selected THEN every segment between two selected nodes SHALL become a line segment.
7. WHEN **Make Curve** is applied with two or more adjacent nodes selected THEN every line segment between two selected nodes SHALL become a cubic with handles at one and two thirds of the line (the shape doesn't change until a handle is moved).
8. End nodes of open subpaths SHALL accept Smooth/Symmetric only on the side that has a segment; Corner is always allowed.
9. Each command SHALL be one undo step, named after the command, and keep the node selection.

### Requirement 2: Break a path at nodes

**User Story:** As a designer, I want to cut a path at a node, so that I can split an outline or open a closed shape at a chosen point.

#### Acceptance Criteria

1. WHEN **Break at Nodes** is run with nodes selected THEN each selected node SHALL be split into two end nodes at the same position, one ending the segment before it and one starting the segment after.
2. IF the node is in a closed subpath THEN the subpath SHALL become open, starting and ending at that node (no new path object).
3. IF the node is in an open subpath (and not one of its end nodes) THEN the subpath SHALL be split into two subpaths of the same path object (a compound path); **Split Path** (Requirement 6) separates them.
4. Selecting an end node of an open subpath SHALL do nothing for that node.
5. After the command both new end nodes SHALL be selected.

### Requirement 3: Join end nodes

**User Story:** As a designer, I want to join two end nodes, so that I can connect paths or close a gap.

#### Acceptance Criteria

1. WHEN **Join Nodes** is run with exactly two end nodes selected THEN they SHALL be merged into one node at their midpoint, keeping the incoming handle of one and the outgoing handle of the other.
2. WHEN **Join with Segment** is run with exactly two end nodes selected THEN a straight segment SHALL be added between them, both nodes staying where they are.
3. IF both end nodes belong to the same open subpath THEN the subpath SHALL become closed.
4. IF they belong to different subpaths of the same path THEN those subpaths SHALL become one, reversing one of them when needed so the direction is continuous.
5. IF they belong to two different paths THEN the result SHALL be one path in the stacking position and style of the path drawn higher; the other path SHALL be removed. Both paths must be in the same container (layer, entered group or Composite).
6. The Node tool SHALL allow selecting nodes on more than one selected path at the same time (today it does only within its edited paths) so that this command can be reached; nodes on non-selected paths are not offered.
7. IF the selection is not exactly two end nodes THEN the commands SHALL be disabled.

### Requirement 4: Delete a segment

**User Story:** As a designer, I want to remove the segment between two nodes, so that I can open a gap without deleting nodes.

#### Acceptance Criteria

1. WHEN **Delete Segment** is run with two adjacent nodes selected THEN the segment between them SHALL be removed; a closed subpath opens there, an open one splits into two subpaths of the same path.
2. IF removing segments leaves a subpath with a single node THEN that node SHALL be removed; if the path ends up empty it SHALL be deleted.

### Requirement 5: Open, close and reverse

**User Story:** As a user, I want to close or open a path and reverse its direction, so that I can make shapes fillable and control dash and marker direction.

#### Acceptance Criteria

1. WHEN **Close Path** is run on selected paths (Select tool) or on nodes of open subpaths (Node tool) THEN each open subpath affected SHALL be closed with a straight segment from its last node to its first; if the two coincide they SHALL be merged into one node.
2. WHEN **Open Path** is run THEN each closed subpath affected SHALL be opened at its first node (Select tool) or at the selected node (same as Break at Nodes in the Node tool).
3. WHEN **Reverse Direction** is run THEN the node order of every affected subpath SHALL be reversed (handles swapped accordingly), without changing the drawn shape; for closed subpaths the start node SHALL stay the same.
4. The commands SHALL work on paths only; with other shapes selected they SHALL apply to the selected paths and ignore the rest, and SHALL be disabled when no path is affected.
5. The Node tool SHALL show the path direction, e.g. by marking each subpath's start node differently, so Reverse has visible feedback.

### Requirement 6: Combine and split

**User Story:** As a designer, I want to combine paths into one compound path and split them apart again, so that I can make holes and manage shapes as one object.

#### Acceptance Criteria

1. WHEN **Combine** is run with two or more paths selected in the same container THEN they SHALL become one path containing all their subpaths, at the stacking position and in the style of the topmost one; transforms SHALL be baked so nothing moves.
2. WHEN **Split Path** is run on a selected path with more than one subpath THEN it SHALL be replaced by one path per subpath, all in the original style, in the original stacking position and order, and all selected.
3. Split SHALL keep holes visually only where that's reasonable: the spec does NOT try to keep a hole attached to its outer subpath (Inkscape's "Break Apart" behaviour; "Split Path" that keeps holes is out of scope).
4. Combine and Split SHALL NOT be offered for Composites, groups, text or images (Object to Path first); rectangles and ellipses SHALL be converted to paths as part of Combine.
5. Each is one undo step.

### Requirement 7: Pen continues and joins paths

**User Story:** As an illustrator, I want to continue an open path from one of its ends with the Pen, so that I can draw a long outline in several sittings.

#### Acceptance Criteria

1. WHEN the Pen tool hovers an end node of an open subpath of a visible, unlocked path in the active container AND no path is in progress THEN the cursor SHALL show "continue path" and the node SHALL be highlighted.
2. WHEN the user clicks (or presses and drags) that end node THEN drawing SHALL continue from it: new nodes are appended to that subpath (from its end, or from its start with the subpath reversed), and dragging shapes that end node's outgoing handle as in the Pen spec.
3. WHEN, while a path is in progress, the user clicks an end node of an open subpath of another path (or the other end of the path being continued) THEN the paths SHALL be joined at that node (Requirement 3 rules for style and stacking) and the result committed; for the path's own other end it SHALL close the subpath.
4. The continued path SHALL keep its style (not the Pen's style), id and stacking position; the edit SHALL be one undo step ("Continue path").
5. Esc while continuing SHALL discard only the new nodes; the original path stays unchanged.

### Shortcuts (to be decided)

Inkscape binds Join (Shift+J), Break (Shift+B), Combine (Ctrl+K), Break Apart (Ctrl+Shift+K), Reverse (Shift+R). Following the shortcut rule, this spec proposes **no shortcuts**, except possibly **Combine / Split** (Ctrl+K / Ctrl+Shift+K) and **Join / Break** (Shift+J / Shift+B, Node tool only). Please decide in review.

## Non-Functional Requirements

### Code Architecture and Modularity
- Segment surgery (node types, break, join, delete segment, close/open, reverse, combine/split) is pure functions in `geometry/` (extending `geometry/nodes.py` or a new `geometry/path_edit.py`), fully unit-tested.
- Operations live in `editing/operations/` (node commands next to `node_editing.py`, path commands in `paths.py`), registered with `@operation`; they reach shapes only through `editing/containers.py`.
- Node tool option buttons are built from the registered operations (like other command buttons), not hard-coded slots.
- The "corner" mark of Requirement 1.5 is either derived (a node is smooth iff its handles are collinear, as today) or stored; if stored it SHALL go into `.p2s` with a version bump and migration, and in SVG as Inkscape's `sodipodi:nodetypes`. The design decides.

### Performance
- Commands run in well under 100 ms on a path with 10k nodes.

### Reliability
- Paths produced by every command round-trip through `.p2s` and SVG unchanged and render identically in resvg (generator check).
- Invalid selections never raise: commands are disabled or do nothing.
- Undo restores exactly the previous segments and node selection.

### Usability
- All new texts translated (German).
- Menu: Path → Combine, Split Path, Close Path, Open Path, Reverse Direction; Path → Nodes → Corner, Smooth, Symmetric, Make Line, Make Curve, Break at Nodes, Join Nodes, Join with Segment, Delete Segment.
- **Out of scope** (later specs): knife/scissors tool, Stroke to Path / Offset / Simplify, align nodes, add nodes by count, auto-smooth node type, live corners, Pen adding/removing nodes on existing paths, Split that keeps holes with their outer subpath.
