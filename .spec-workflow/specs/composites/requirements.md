# Requirements Document

## Introduction

A **Composite** is a shape built from other shapes, its **parts**, that stays editable. Parts are stacked bottom to top. The bottom part is the starting area, and every part above it has a **mode** that says how it changes everything below it: **Add**, **Subtract**, **Intersect** or **Exclude**. Outside its edit mode a Composite looks and behaves like a single shape: you see only the resulting outline, painted in the Composite's own style, and you can select, move, scale, rotate, restyle and delete it as one. **Entering** the Composite (double-click) opens an edit mode where its parts become visible and editable: move them, reshape them, change their mode or order, draw new parts, delete parts. The result updates live. **Leaving** the edit mode returns to the single-shape view. Nothing is baked until the user explicitly flattens the Composite.

Composites can contain Composites (nesting), so complex constructions can be built and refined level by level.

The geometry comes from the full-booleans spec: `geometry.booleans.combine_parts` evaluates exactly this ordered list of `(outline, mode)` parts.

## Alignment with Product Vision

- **Principle 3, Non-destructive by default**: booleans stay editable instead of replacing shapes for good, the product vision's own example ("editable booleans").
- **Core pillar 5, Path editing & construction**: a shape-construction workflow beyond destructive booleans, in the spirit of a shape builder.
- **Principle 4, Own format for fidelity, SVG for exchange**: SVG gets the correct visible result for every other tool, plus a PressToShape definition that restores the editable Composite on reopening; edits made elsewhere degrade predictably.
- **Target users**: illustrators and logo/icon designers build shapes by adding and cutting basic forms; non-destructive construction lets them iterate without redrawing.

## Requirements

### Requirement 1 — Creating a Composite

**User Story:** As a designer, I want to turn selected shapes into a Composite, so that I can combine them without losing the originals.

#### Acceptance Criteria

1. WHEN two or more shapes with a vector outline (rectangles, ellipses, paths, Composites) are selected AND the user runs Path → Make Composite (Ctrl+Alt+C) THEN the system SHALL replace them with one Composite whose parts are those shapes in their current bottom-to-top order, the bottom one as the base and every other part in mode **Add**.
2. WHEN the user runs Path → Make Composite ▸ Add / Subtract / Intersect / Exclude THEN the system SHALL create the Composite with every part above the base in that mode (the non-destructive counterparts of union, difference, intersection and exclude).
3. WHEN a Composite is created THEN it SHALL take the bottom part's style and its place (layer and z-position), be selected, and be one undo step labelled "Make Composite".
4. WHEN the selection contains text THEN text SHALL be left out (as with booleans: Object to Path first); IF fewer than two shapes remain THEN the commands SHALL be disabled.

### Requirement 2 — A Composite as one shape

**User Story:** As a designer, I want a Composite to behave like any other shape outside its edit mode, so that it fits into my normal workflow.

#### Acceptance Criteria

1. WHEN a Composite is shown outside its edit mode THEN the canvas and PNG export SHALL draw only its resulting outline, filled and stroked with the Composite's own style; its parts SHALL NOT be drawn.
2. WHEN the user clicks, rubber-band selects or hovers a Composite THEN hit-testing SHALL use the resulting outline; IF the result is empty THEN the Composite SHALL still be selectable through the bounds of its parts and SHALL show a dashed placeholder outline of those bounds while selected, so it can't get lost.
3. WHEN a Composite is moved, scaled or rotated with the Select tool, the handles or the panel THEN all its parts SHALL be transformed with it (one undo step), so the result keeps its shape relative to the parts.
4. WHEN fill, stroke or stroke width are changed for a selected Composite THEN the Composite's own style SHALL change; the parts' styles SHALL stay as they are.
5. WHEN a Composite is used in a destructive boolean or as a part of another Composite THEN its resulting outline SHALL be used.
6. WHEN a Composite is deleted, copied by undo/redo or saved THEN its parts SHALL go with it.

### Requirement 3 — Edit mode

**User Story:** As a designer, I want to enter a Composite to change its parts and see the result update, then leave again.

#### Acceptance Criteria

1. WHEN the user double-clicks a Composite with the Select tool, or selects one and presses Enter, THEN the system SHALL enter its edit mode.
2. WHILE in edit mode THEN the canvas SHALL show the live result in the Composite's style, every part as an outline over it (styled by mode so Add, Subtract, Intersect and Exclude are distinguishable at a glance), and everything outside the Composite dimmed and not selectable.
3. WHILE in edit mode THEN the Select tool, handles, Node tool and selection panel SHALL work on the parts exactly as they work on shapes on a layer (select, move, scale, rotate, edit nodes, edit geometry fields), and the result SHALL update live during drags.
4. WHILE in edit mode AND the user draws a new rectangle, ellipse or path THEN it SHALL become a new top-most part of the Composite in the current **new-part mode** (Add by default), shown and changeable in the tool options.
5. WHILE in edit mode THEN deleting parts SHALL remove them; IF the base part is deleted THEN the next part SHALL become the base; IF the last part is deleted THEN the Composite SHALL be deleted and edit mode left.
6. WHEN the user presses Esc with nothing selected, double-clicks outside the Composite, or uses the edit-mode bar's "Done" button, THEN the system SHALL leave edit mode one level and select the Composite.
7. WHILE in edit mode THEN a bar above the canvas SHALL show where the user is (e.g. "Layer 1 › Composite › Composite") with a way to leave to any level.
8. WHEN entering or leaving edit mode THEN it SHALL NOT create undo steps; every change made inside SHALL be undoable as usual, and undoing past the Composite's creation SHALL leave edit mode.

### Requirement 4 — Part modes and order

**User Story:** As a designer, I want to change how each part combines and in which order, so that I can rework the construction.

#### Acceptance Criteria

1. WHILE in edit mode AND one or more parts are selected THEN the selection panel SHALL show their mode (Add, Subtract, Intersect, Exclude) and let the user change it; the result SHALL update immediately (one undo step per change).
2. WHEN the base part is selected THEN its mode control SHALL be shown as "Base" and disabled, since the base is the starting area whatever its mode.
3. WHILE in edit mode THEN Raise (Page Up), Lower (Page Down), Raise to Top (Home) and Lower to Bottom (End) SHALL change the order of the selected parts, changing the result accordingly; outside edit mode the same commands SHALL change the z-order of shapes within their layer.

### Requirement 5 — Nesting

**User Story:** As a designer, I want Composites inside Composites, so that I can build complex shapes from simpler constructions.

#### Acceptance Criteria

1. WHEN a part is itself a Composite THEN it SHALL take part with its resulting outline and its own parts SHALL stay hidden.
2. WHILE in a Composite's edit mode AND the user double-clicks a part that is a Composite THEN the system SHALL enter that Composite (one level deeper); the bar SHALL show the full path.
3. WHEN any change happens at any depth THEN the results of all enclosing Composites SHALL update.
4. WHEN Make Composite runs inside edit mode on selected parts THEN they SHALL become a nested Composite in their place (taking the bottom one's mode).

### Requirement 6 — Release and flatten

**User Story:** As a designer, I want to undo the construction or bake it, so that I'm never stuck with a Composite.

#### Acceptance Criteria

1. WHEN the user runs Path → Release Composite on selected Composites THEN each SHALL be replaced by its parts as ordinary shapes, in order and with their own styles, in the Composite's place, all selected.
2. WHEN the user runs Path → Flatten Composite (or Object to Path) on selected Composites THEN each SHALL be replaced by a plain path with the resulting outline and the Composite's style.
3. WHEN either command runs THEN it SHALL be one undo step.

### Requirement 7 — Saving to SVG

**User Story:** As a user exchanging files with other tools, I want other programs to show the right result and PressToShape to restore the editable Composite.

#### Acceptance Criteria

1. WHEN a document with Composites is saved as SVG THEN each Composite SHALL be written so that any SVG viewer or Inkscape renders exactly its resulting outline with the Composite's style.
2. WHEN saving THEN the parts, their modes and order (including nested Composites) SHALL be stored in PressToShape-namespaced data that other tools ignore and keep.
3. WHEN a file saved by PressToShape is opened again THEN every Composite SHALL be restored editable with identical parts, modes, order, styles and result.
4. IF the visible result was changed by another program (it no longer matches the stored parts) THEN the system SHALL open it as a plain path showing the edited result and report that the Composite's parts were discarded, so external edits are never silently overwritten.
5. WHEN Composites are saved and reopened THEN pytest SHALL cover the round trip, including nesting and the mismatch case.

## Non-Functional Requirements

### Code Architecture and Modularity
- Model: a new frozen `CompositeShape` holding its parts and their modes, a member of the `Shape` union; edits replace it via `dataclasses.replace`, so snapshot undo keeps working unchanged.
- Edit-mode location (which Composite, at which depth) is app state in `models/`, changed only by operations; it is not part of undo history.
- Geometry stays in `geometry/` (`combine_parts`), rendering and picking in `render/`, commands in `editing/operations/` (a `composites` module), the edit-mode bar in `views/`; tools work on "the current container" (a layer or a Composite) instead of assuming layers. Architecture test rules stay as they are.

### Performance
- Result outlines are cached per frozen Composite (like `PathCache` does for paths) and recomputed only when the Composite or a part changes.
- Live result updates while dragging a part in edit mode SHALL stay fluid for Composites with up to ~20 parts of typical complexity.
- Documents without Composites SHALL not get slower (canvas benchmark within noise).

### Reliability
- Every change inside and outside edit mode is undoable; undo/redo never leaves the app in an edit mode for a Composite that no longer exists.
- SVG round trips are lossless for PressToShape-only workflows and never silently discard external edits.

### Usability
- Edit mode is obvious at a glance: dimmed surroundings, mode-styled part outlines and the location bar.
- Modes use the same names as the boolean commands' non-destructive counterparts: Add, Subtract, Intersect, Exclude.
- Status bar hints explain how to enter and leave edit mode.
