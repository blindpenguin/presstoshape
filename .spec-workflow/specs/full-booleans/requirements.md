# Requirements Document

## Introduction

PressToShape can combine selected shapes with **union** and **difference** today. This spec completes the boolean set with **intersection**, **exclude** (XOR) and **divide**, makes all operations work the same way from menus, shortcuts and the tool strip, and adds a pure geometry function that evaluates an *ordered list of parts, each with its own mode*. That function is the foundation for the planned **Composite** feature (a separate, later spec: non-destructive shapes built from add/subtract/intersect/exclude parts that stay editable).

All operations in this spec are destructive: they replace the selected shapes with the result, as union and difference do now. Every operation is one undo step.

## Alignment with Product Vision

- **Core pillar 5, Path editing & construction: "full boolean set"** is delivered here; the shape builder and non-destructive booleans build on it.
- **Principle 3, Non-destructive by default ("editable booleans")**: the ordered-parts evaluation in Requirement 5 is what the Composite spec will use to keep booleans editable.
- **People leaving Illustrator / Inkscape** expect intersection, exclusion and divide next to union and difference, with the same shortcuts Inkscape uses.

## Requirements

### Requirement 1 — Intersection

**User Story:** As a designer, I want to keep only the area where selected shapes overlap, so that I can cut a shape to the outline of another.

#### Acceptance Criteria

1. WHEN two or more shapes with a vector outline are selected AND the user runs Path → Intersection (Ctrl+*) THEN the system SHALL replace them with one path covering only the area shared by **all** of them.
2. IF the selected shapes have no area in common THEN the system SHALL remove them and leave nothing, select nothing, and report "Intersection is empty" in the status bar (still one undo step).
3. WHEN the result is created THEN it SHALL take the style, layer and z-position of the bottom-most selected shape, as union and difference do.

### Requirement 2 — Exclude

**User Story:** As a designer, I want overlapping areas to become holes, so that I can make interlocking or checkerboard shapes.

#### Acceptance Criteria

1. WHEN two or more shapes are selected AND the user runs Path → Exclude (Ctrl+^) THEN the system SHALL replace them with one path covering the areas covered by an **odd** number of the selected shapes (overlaps of two become holes, of three are filled again, and so on).
2. WHEN the result is created THEN it SHALL take the style, layer and z-position of the bottom-most selected shape.
3. IF the result is empty (e.g. two identical shapes) THEN the system SHALL behave as Requirement 1.2 with the message "Exclude is empty".

### Requirement 3 — Divide

**User Story:** As an illustrator, I want overlapping shapes split into separate pieces along all their edges, so that I can color or delete each region on its own.

#### Acceptance Criteria

1. WHEN two or more shapes are selected AND the user runs Path → Divide (Ctrl+/) THEN the system SHALL replace them with one path per distinct region formed by their outlines: every area covered by a different combination of the selected shapes becomes its own piece.
2. WHEN a region consists of several disconnected areas THEN each connected area SHALL become a separate piece; holes SHALL stay part of the piece that surrounds them.
3. WHEN a piece is created THEN it SHALL take the style of the **top-most** selected shape covering it (what the user saw there before dividing).
4. WHEN pieces are created THEN they SHALL be placed in the layer and at the z-position of the bottom-most selected shape, ordered so that pieces from higher source shapes stay above pieces from lower ones, and all pieces SHALL be selected afterwards.
5. WHEN Divide runs THEN it SHALL be one undo step, and the status bar SHALL report the number of pieces ("Divided into 5 pieces").
6. IF dividing would produce pieces smaller than a minimum area (float noise from pathops) THEN those slivers SHALL be dropped.

### Requirement 4 — Consistent commands for all boolean operations

**User Story:** As a user, I want all five operations to behave and look alike, so that I can find and use them the same way.

#### Acceptance Criteria

1. WHEN the Path menu is opened THEN it SHALL list Union, Difference, Intersection, Exclude and Divide (in that order), followed by a separator and Object to Path.
2. WHEN the tool strip is shown THEN it SHALL offer all five operations as icon buttons next to the existing union/difference buttons, with Tabler icons and tooltips that include the shortcut.
3. WHEN shortcuts are assigned THEN they SHALL follow Inkscape: Union Ctrl++, Difference Ctrl+-, Intersection Ctrl+*, Exclude Ctrl+^, Divide Ctrl+/.
4. WHEN fewer than two selected shapes have a vector outline THEN all five commands SHALL be disabled, as union and difference are today. Text stays excluded from booleans (Object to Path first), unchanged from today.
5. WHEN any operation runs on shapes with transforms (rotated rectangles, ellipses) THEN it SHALL use their transformed outlines, as today.
6. WHEN any operation finishes THEN its undo step SHALL carry the operation's name (e.g. "Undo Intersection").

### Requirement 5 — Ordered parts evaluation (foundation for Composites)

**User Story:** As a developer of the upcoming Composite feature, I want one pure function that combines an ordered list of outlines, each with its own mode, so that destructive booleans and live Composites share the same geometry.

#### Acceptance Criteria

1. WHEN given an ordered list of parts `(outline, mode)` with mode in add, subtract, intersect, exclude THEN the function SHALL start from the first part's outline and apply each following part with its mode to the accumulated result, bottom to top.
2. WHEN the first part's mode is not "add" THEN it SHALL still be treated as the starting area (the first part always defines the base).
3. WHEN union, difference, intersection and exclude run on a selection THEN they SHALL be computed through this function (all parts with the same mode), so both paths stay consistent.
4. WHEN the function runs THEN it SHALL be Qt-free, live in `geometry/`, and be covered by pytest, including empty results and parts that don't overlap.

## Non-Functional Requirements

### Code Architecture and Modularity
- Geometry stays in `presstoshape/geometry/` (pure, Qt-free); commands in `presstoshape/editing/operations/paths.py` (or a new `booleans` operations module if `paths.py` would grow past one concern), registered with ids `path.intersection`, `path.exclude`, `path.divide`; shortcuts and icons only in `views/keymap.py`.
- No changes to the model: results are plain `PathShape`s.

### Performance
- Booleans on a typical selection (up to ~20 shapes with up to a few hundred segments each) SHALL finish in well under a second; divide with N shapes SHALL not grow worse than roughly quadratic in N.

### Reliability
- Results go through the same float32 rounding as today; sliver pieces from rounding are dropped (Requirement 3.6).
- Every operation is a single undo step; undo restores the original shapes, ids, styles and order exactly.

### Usability
- Status bar messages name the operation and the outcome (empty result, piece count).
- Menu, tool strip and shortcuts follow the conventions users know from Inkscape.
