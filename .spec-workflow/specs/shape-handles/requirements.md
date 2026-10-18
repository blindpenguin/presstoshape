# Requirements Document

## Introduction

Today shapes can only be resized or repositioned precisely through the spinboxes in the Select tool options panel; on the canvas the Select tool can only move whole shapes, and the cursor is a plain arrow everywhere. This spec adds direct manipulation on the canvas:

1. **Transform handles** on the selection: eight scale handles around the selection's bounding box and rotation zones just outside its corners.
2. **Per-shape transforms** in the model, so a rotated rectangle stays a rectangle, a rotated ellipse stays an ellipse and rotated text stays editable text.
3. **A Node tool** for editing paths directly: drag anchors and bezier control points, select several nodes, insert and delete nodes, plus an **Object to Path** command so rectangles, ellipses and text can be node-edited too.
4. **Cursor feedback** that tells the user what a press will do at the current pointer position (move, scale in which direction, rotate, edit a node, draw, type).

## Alignment with Product Vision

- **Core pillar 6, Precision & layout: "transforms with handles"**, delivered here for scale and rotate.
- **Core pillar 5, Path editing & construction: "node/handle editing"**, delivered here in a first version.
- **Target users**: designers need precise path editing, and people leaving Illustrator or Inkscape expect bounding-box handles, rotate-by-corner and a node tool to work as they know them.
- **Principle 1, Artists first**: manipulating shapes directly on the canvas, with a cursor that announces the action, keeps the user's eyes on the drawing instead of the panel.
- **Principle 5, Inkscape interop**: per-shape transforms are written and read as SVG `transform` attributes, so rotated shapes round-trip through Inkscape as the same element type instead of being flattened to paths.
- **Tech debt in tech.md** ("no per-shape transforms", "non-translation transforms are flattened to paths") is resolved for rect, ellipse, path and text.

## Requirements

### Requirement 1 — Selection transform handles

**User Story:** As a designer, I want handles around my selection, so that I can see what is selected and resize it directly on the canvas.

#### Acceptance Criteria

1. WHEN one or more shapes are selected with the Select tool THEN the system SHALL draw the selection's bounding box with eight square scale handles (four corners, four edge midpoints) at a constant screen size independent of zoom.
2. WHEN exactly one shape is selected AND it has a rotation THEN the bounding box and handles SHALL be drawn in the shape's own rotated frame (aligned with the shape), not as an axis-aligned box around it.
3. WHEN several shapes are selected THEN the system SHALL draw one axis-aligned box around all of them, and keep the per-shape outline indicator that exists today.
4. WHEN the selection is very small on screen THEN handles SHALL stay grabbable and SHALL NOT overlap so that the shape itself can no longer be dragged (e.g. edge handles hidden below a minimum on-screen size).
5. WHEN handles are drawn THEN they SHALL be overlays only: never part of the document, the saved SVG or the PNG export.
6. WHEN a gesture is in progress (move, scale, rotate) THEN the box and handles SHALL follow the live result.

### Requirement 2 — Scaling with handles

**User Story:** As a designer, I want to drag a handle to resize, so that I can shape objects by eye without typing numbers.

#### Acceptance Criteria

1. WHEN the user drags a corner handle THEN the system SHALL scale the selection in both axes with the opposite corner fixed.
2. WHEN the user drags an edge handle THEN the system SHALL scale only along that edge's axis with the opposite edge fixed.
3. WHEN Shift is held during a corner drag THEN the system SHALL keep the aspect ratio; WHEN Shift is held during an edge drag THEN the other axis SHALL scale by the same factor (uniform scale).
4. WHEN Alt is held THEN the system SHALL scale about the selection's center instead of the opposite handle.
5. WHEN a handle is dragged past the opposite side THEN the selection SHALL flip (mirror) along that axis.
6. WHEN the drag is in progress THEN the canvas SHALL show the live result; WHEN released THEN the system SHALL commit the result in one controller call that forms one undo step; WHEN Esc is pressed during the drag THEN the system SHALL cancel and leave the document unchanged.
7. WHEN a rectangle or ellipse without rotation is scaled THEN the result SHALL remain a rectangle/ellipse with updated position and size (the panel shows the new X/Y/W/H or center/radii).
8. WHEN a path is scaled THEN its segments SHALL be scaled; stroke width SHALL stay unchanged (no stroke scaling in this spec).
9. WHEN text is scaled THEN the system SHALL scale uniformly: the font size and anchor position change proportionally; non-uniform scaling SHALL be applied as uniform (by the larger factor) for text. WHEN a selection containing text is scaled non-uniformly THEN the other shapes SHALL scale as requested and the text SHALL scale uniformly about its own anchor mapped through the scale.
10. IF scaling would produce zero width or height THEN the system SHALL clamp to a minimum size instead of producing degenerate geometry, and a shape with zero extent in one axis (e.g. a horizontal line) SHALL not scale in that axis.

### Requirement 3 — Rotating with handles

**User Story:** As an illustrator, I want to rotate objects by dragging near a corner, so that I can angle shapes without leaving the canvas.

#### Acceptance Criteria

1. WHEN the pointer is in a rotation zone (a ring just outside a corner handle) and the user drags THEN the system SHALL rotate the selection about the center of its bounding box by the angle swept by the pointer.
2. WHEN Shift is held during rotation THEN the angle SHALL snap to 15° increments.
3. WHEN rotation is in progress THEN the canvas SHALL show the live result and the status bar SHALL show the current angle; release commits one undo step; Esc cancels.
4. WHEN a rectangle, ellipse or text shape is rotated THEN it SHALL stay that shape type with a rotation in its transform; its fill, stroke and text content stay editable.
5. WHEN a path is rotated THEN the system MAY bake the rotation into its segments (paths stay transform-free) as long as the visible result is identical.
6. WHEN a rotated shape is selected alone THEN the Select tool options panel SHALL show and allow editing its rotation angle (degrees); the existing geometry fields SHALL refer to the shape's own unrotated frame.
7. WHEN a rotated shape is later scaled with a handle THEN scaling SHALL happen along the shape's own axes (Requirement 1.2), keeping it a rotated rectangle/ellipse rather than a skewed one.
8. WHEN several shapes with different rotations are scaled non-uniformly together THEN the system SHALL produce the visually correct result (which may include skew in a shape's transform) rather than an approximation.

### Requirement 4 — Per-shape transforms in model, rendering and file I/O

**User Story:** As an Inkscape user, I want rotated shapes to stay real rectangles, ellipses and text, so that my files keep their structure when I move them between tools.

#### Acceptance Criteria

1. WHEN the model is extended THEN every shape type SHALL be able to carry an affine transform (identity by default) applied on top of its geometry; shape geometry stays in document coordinates when the transform is identity, so existing documents are unchanged.
2. WHEN shapes with transforms are rendered on the canvas or exported to PNG THEN they SHALL appear transformed, with canvas and export matching.
3. WHEN shapes with transforms are hit-tested, rubber-band selected, outlined for selection bounds or combined with booleans THEN the transform SHALL be taken into account.
4. WHEN moving a shape with a non-identity transform THEN the move SHALL keep the shape's rotation and only translate it.
5. WHEN saving SVG THEN a non-identity transform SHALL be written as the element's `transform` attribute (as `rotate(...)` where that is exact, else `matrix(...)`) and identity SHALL write no attribute.
6. WHEN opening SVG THEN `rect`, `ellipse`/`circle` and `text` elements under a rotate/scale/skew transform SHALL be imported as the same shape type with that transform, instead of being flattened to paths; paths keep being imported with the transform applied to their segments.
7. WHEN a veccy-saved SVG with rotated shapes is reopened THEN geometry, transforms, styles and layers SHALL be preserved (round trip covered by pytest).

### Requirement 5 — Node tool for paths

**User Story:** As a designer, I want to edit a path's points and curve handles directly, so that I can refine shapes precisely.

#### Acceptance Criteria

1. WHEN the user activates the Node tool (toolbar, Tools menu, shortcut `N`) THEN the system SHALL show the anchor points of every selected path, and clicking a path SHALL select it and show its anchors.
2. WHEN the user clicks an anchor THEN that node SHALL become selected (Shift-click toggles it in the node selection, drag on empty space rubber-band selects nodes of the edited paths); selected nodes SHALL be drawn distinctly from unselected ones.
3. WHEN nodes are selected THEN the system SHALL show the bezier control points of the curve segments adjacent to the selected nodes, connected to their anchor by a line.
4. WHEN the user drags an anchor THEN all selected nodes SHALL move with their attached control points, live, and release SHALL commit one undo step.
5. WHEN the user drags a control point THEN only that control point SHALL move; WHEN the opposite control point of the same anchor is collinear (smooth node) THEN it SHALL rotate to stay collinear while keeping its own length; Alt-drag SHALL move the control point independently (break smoothness).
6. WHEN the user double-clicks on a path segment THEN the system SHALL insert a node at that point without changing the path's shape (curve subdivision).
7. WHEN the user presses Delete/Backspace with nodes selected THEN the system SHALL remove those nodes (joining their neighbours) instead of deleting the shape; IF fewer than two nodes would remain in a subpath THEN that subpath SHALL be removed; IF the path would become empty THEN the shape SHALL be deleted.
8. WHEN Esc is pressed THEN the system SHALL cancel an in-progress node drag, else clear the node selection, else the shape selection.
9. WHEN the Node tool is active AND a non-path shape (rect, ellipse, text) is selected THEN the system SHALL show its bounding outline only and the status bar SHALL hint at Object to Path.
10. WHEN node edits happen THEN they SHALL be Qt-free geometry/controller logic covered by pytest (move nodes, insert, delete, smooth handle).

### Requirement 6 — Object to Path

**User Story:** As a designer, I want to turn a rectangle, ellipse or text into a path, so that I can node-edit it.

#### Acceptance Criteria

1. WHEN the user chooses Object → Object to Path (shortcut Ctrl+Shift+C) THEN each selected rectangle, ellipse and text shape SHALL be replaced by a path with the same visible outline (transform baked in), style, layer and paint order, and the new paths SHALL stay selected.
2. WHEN the selection contains no convertible shape THEN the command SHALL be disabled.
3. WHEN the conversion happens THEN it SHALL be one undo step.

### Requirement 7 — Cursor feedback

**User Story:** As an artist, I want the cursor to show what will happen when I press, so that I don't have to guess where to grab.

#### Acceptance Criteria

1. WHEN the Select tool is active AND the pointer is over a scale handle THEN the cursor SHALL be the resize cursor matching that handle's on-screen direction (horizontal, vertical, or one of the two diagonals), taking the selection's rotation into account by picking the nearest of the four directions.
2. WHEN the pointer is in a rotation zone THEN the cursor SHALL be a rotate cursor (a custom vector cursor from the app's icon set, rendered at the display's pixel ratio).
3. WHEN the pointer is over a shape that a press would grab (selected or not) THEN the cursor SHALL be a move cursor; over empty canvas it SHALL be the normal arrow.
4. WHEN the Node tool is active THEN the cursor SHALL indicate a grabbable node or control point when hovering one, and a path-insertion hint over a segment of an edited path, else the arrow.
5. WHEN a drag gesture is in progress THEN the cursor SHALL stay the one the gesture started with until release (no flicker while crossing other handles or shapes).
6. WHEN drawing tools are active THEN their cursors SHALL stay as today (crosshair for pen/rectangle/ellipse, I-beam for text); WHEN panning THEN the closed hand SHALL show and the hover cursor SHALL be restored afterwards.
7. WHEN the selection, zoom or scroll changes under a stationary pointer (e.g. after undo, keyboard zoom) THEN the cursor SHALL update to match what is now under the pointer.
8. WHEN the cursor shape is chosen THEN the decision SHALL come from Qt-free logic (a hover query on the gesture/hit-test layer returning a cursor type) that the view maps to Qt cursors, so it is covered by pytest.

## Non-Functional Requirements

### Code Architecture and Modularity
- Follow CLAUDE.md MVC rules: transforms and node edits are applied in `controllers/` (pure geometry in `geometry.py` or a new Qt-free module), drawing of handles in `render/`, gesture state in `views/canvas_gestures.py` or a sibling Qt-free gesture module; no Qt in `models/`, `controllers/`, `render/`.
- Handle geometry and hit-testing (which handle or node is under a point, at screen-constant size) is Qt-free and lives in `render/`.
- `canvas_gestures.py` SHALL not grow into one large class: per-tool or per-gesture logic (select/transform, node edit) is split into focused modules.
- Every committed gesture goes through one controller call that calls `_checkpoint()` before mutating and `_notify()` after.

### Performance
- Live scale/rotate/node-drag previews SHALL stay fluid with the 10k-shape benchmark document: the preview must not force re-recording the whole document picture on every mouse move (e.g. draw the moving shapes as transient overlays, as moving does today).
- Hover queries for cursor feedback SHALL stay under a few ms per mouse move with 10k shapes (handles are checked before shape hit-testing; shape hit-testing only when needed).

### Reliability
- No degenerate geometry (NaN, zero-size rect/ellipse, singular transform) can be committed by any gesture.
- Undo/redo restores transforms and node edits exactly.
- Existing pytest suite keeps passing; SVG files saved before this spec open unchanged.

### Usability
- Modifiers follow common vector-editor conventions: Shift = constrain (aspect ratio / 15° / toggle in selection), Alt = from center / break handle symmetry, Esc = cancel.
- Handles and nodes use the theme's selection color with a contrasting outline so they stay visible on any fill, at constant screen size.
- The Select tool options hint text and the status bar describe the new gestures.
