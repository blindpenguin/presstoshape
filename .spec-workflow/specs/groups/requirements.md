# Requirements Document

## Introduction

A **group** bundles shapes so they act as one object: click selects the whole group, handles move, scale and rotate everything in it together, delete, copy and arrange treat it as one. **Entering** a group (double-click) works on the shapes inside it individually, like entering a Composite, but without combining their outlines: every shape inside keeps its own style and is drawn as it is. Groups can contain any shape, Composites and other groups.

Groups also make SVG import faithful to the structure of the file: today every `<g>` from Illustrator, Inkscape or Figma is flattened, so a logo made of 40 shapes arrives as 40 loose shapes. With groups it arrives as the designer built it, and a group's opacity is applied to the group as a whole instead of being approximated per shape.

The Composite edit mode already provides what entering needs: the active container (`editing/containers.py`), the `edit_path` of entered objects, the bar above the canvas, and leaving with Esc / Done. Groups reuse it.

## Alignment with Product Vision

- **Feature gap list, P1 "Editing"**: "Groups: group/ungroup (Ctrl+G), enter a group to edit (could reuse the Composite edit-mode machinery)". First item of the suggested order.
- **Target users**: designers making logos and icons organize shapes in groups; people leaving Illustrator and Inkscape expect groups in their files to stay groups.
- **Success metric, Interop**: "common Inkscape and Illustrator-exported SVG files open correctly", which includes their structure.
- **Principle 2, Professional depth, approachable surface**: a familiar concept with the familiar shortcuts.

## Requirements

### Requirement 1: Group and ungroup

**User Story:** As a designer, I want to group shapes and ungroup them again, so that I can handle parts of a drawing as one object.

#### Acceptance Criteria

1. WHEN one or more shapes are selected AND the user runs Object → Group (Ctrl+G) THEN the system SHALL replace them with one group containing them in their current bottom-to-top order, placed at the z-position of the top-most selected shape, and select the group. One undo step, "Group".
2. WHEN the selected shapes come from different layers THEN the group SHALL be placed in the layer of the top-most selected shape.
3. WHEN one or more groups are selected AND the user runs Object → Ungroup (Ctrl+Shift+G) THEN each group SHALL be replaced by its shapes at its z-position, and those shapes SHALL be selected. One undo step, "Ungroup".
4. WHEN a group with an opacity below 100 % is ungrouped THEN its opacity SHALL be multiplied into each of its shapes (the closest look without the group).
5. Group SHALL be disabled with nothing selected; Ungroup SHALL be disabled when no group is selected.

### Requirement 2: A group as one object

**User Story:** As a designer, I want a group to behave like a single shape until I enter it, so that I can move and arrange it as a whole.

#### Acceptance Criteria

1. WHEN the user clicks or rubber-band selects with the Select tool THEN a group SHALL be selected as a whole; clicking any visible shape inside it selects the group.
2. WHEN a group is moved, scaled or rotated with the Select tool, handles or the panel THEN every shape inside SHALL be transformed with it, keeping their positions relative to each other. One undo step, as for single shapes.
3. Delete, copy, cut, paste, duplicate, Alt+drag, raise and lower SHALL treat a selected group as one object, with everything inside it.
4. The selection panel SHALL show "Group" (or "Group of {count} objects") for a single selected group, its position and size, and the style controls:
   - the group's own **opacity** applies to the group as a whole (its shapes are flattened first, then made transparent, as SVG renders group opacity);
   - fill, stroke and the other style fields SHALL apply to every shape inside the group (recursively), as in Inkscape and Illustrator. The fields show the values of the first shape inside.
5. Hit-testing, bounds and the selection frame SHALL use the shapes inside: the group is hit where any of its shapes is hit.
6. Destructive booleans, divide and Make Composite SHALL leave groups out (like text today) and say so in the status bar ("Ungroup first"); IF fewer than two shapes remain THEN the commands stay disabled.
7. An empty group (all shapes inside deleted) SHALL be removed.

### Requirement 3: Entering a group

**User Story:** As a designer, I want to work on the shapes inside a group without ungrouping it, so that the group stays intact.

#### Acceptance Criteria

1. WHEN the user double-clicks a group with the Select tool, or selects one and presses Enter, THEN the system SHALL enter the group.
2. WHILE inside a group THEN the shapes inside SHALL be selectable and editable with every tool exactly as on a layer (select, move, scale, rotate, node editing, styling, arrange, delete, copy and paste, select all), and everything outside the group SHALL be dimmed and not selectable, as in a Composite's edit mode.
3. WHILE inside a group THEN new shapes drawn or pasted SHALL be added to the group.
4. WHILE inside a group THEN double-clicking a nested group or Composite SHALL enter it; the bar above the canvas SHALL show the path (e.g. "Layer 1 › Group › Composite") with a way back to any level.
5. WHEN the user presses Esc with nothing selected, double-clicks outside the group, or uses "Done" THEN the system SHALL leave one level and select the group that was left.
6. Entering and leaving SHALL NOT be undo steps; changes made inside SHALL be undoable as usual, and undo SHALL leave a group that no longer exists.
7. WHILE inside a Composite THEN a group pasted into it SHALL become separate parts (its shapes, with text turned into paths as pasting text does today), since Composite parts are outlines.

### Requirement 4: Drawing and export

**User Story:** As an artist, I want groups to look exactly like their shapes, with transparency applied to the group as a whole.

#### Acceptance Criteria

1. A group SHALL be drawn as its shapes in order, each with its own style; the canvas, PNG export and the recorded-picture replay SHALL agree.
2. WHEN a group's opacity is below 100 % THEN its shapes SHALL be composited together first and then drawn with that opacity (overlapping shapes inside don't show through each other).
3. A group at 100 % opacity SHALL cost no more per frame than its shapes drawn loose.
4. While a group is dragged, scaled or rotated THEN the live preview SHALL show all its shapes, as for single shapes.

### Requirement 5: SVG

**User Story:** As someone leaving Illustrator or Inkscape, I want the groups in my files to stay groups, so that the drawing keeps the structure its designer gave it.

#### Acceptance Criteria

1. WHEN an SVG is opened or pasted THEN every `<g>` that isn't an Inkscape layer, and every `<a>`, SHALL become a group with the shapes it contains; empty groups SHALL be dropped.
2. Group opacity SHALL be imported as the group's opacity; the "transparent group was approximated" note SHALL no longer appear for groups.
3. WHEN a group has a transform THEN its shapes SHALL be placed by it (the group itself keeps no transform, like a Composite).
4. Nested Inkscape layers (a layer inside a layer) SHALL become groups inside the outer layer, since PressToShape has no nested layers yet.
5. Each `<use>` of a group or `<symbol>` SHALL become a group of the copied shapes; `<use>` of a single shape stays a single shape.
6. WHEN saved as SVG THEN a group SHALL be written as `<g>` with its opacity when below 100 %, and its shapes inside; the clipboard SVG likewise. Inkscape SHALL show them as groups.
7. Clip paths and masks on groups stay unsupported and noted, as today.

### Requirement 6: Native format and clipboard

**User Story:** As a user, I want groups to survive saving, reopening, copying and undo exactly.

#### Acceptance Criteria

1. `.p2s` SHALL store groups with their shapes and opacity, in a new format version with a migration from the previous one (no change needed for old files), a sample file and a `docs/file-format.md` row.
2. A group entered while saving SHALL be entered again after reopening, as the entered Composite is today.
3. Copy and paste inside PressToShape SHALL keep groups (with fresh ids for everything inside).
4. Every group operation SHALL be undoable; undo snapshots stay cheap (shared frozen shapes).

## Non-Functional Requirements

### Code Architecture and Modularity
- A frozen `GroupShape` in `models/shapes.py` next to `CompositeShape`; transforms, translation, bounds and drawing recurse into it like Composites.
- The active container and edit path generalize from "Composite" to "container shape" (Composite or group) in `editing/containers.py`, so operations keep reaching shapes only through `pickable_shapes` / `change_container`.
- Group operations in `editing/operations/groups.py`, registered with ids, menu entries and shortcuts in the keymap.

### Performance
- Opening an SVG with thousands of shapes in nested groups SHALL not be noticeably slower than today.
- `scripts/bench_canvas.py` numbers SHALL stay the same for documents without groups, and comparable when the same shapes are grouped.

### Reliability
- Malformed or deeply nested groups in foreign SVG never crash the import; nesting depth is bounded.
- Everything the app can save opens again (round-trip tests for nested groups, groups in Composites' neighbourhood, entered groups).

### Usability
- Familiar shortcuts: Ctrl+G and Ctrl+Shift+G (frequent editing actions, so they qualify for shortcuts).
- All new UI text is translated (English source + German).
- The Layers panel tree (showing objects inside layers and groups) is out of scope; it comes with the Layers panel upgrade.
