# Requirements Document

## Introduction

SVG files made in other programs often open in PressToShape looking wrong, and nothing tells the user why. Illustrator exports style shapes through CSS classes, so everything opens black. Holes in `fill-rule="evenodd"` shapes are filled in. Semi-transparent artwork turns opaque, dashed lines turn solid, rounded rectangles get sharp corners, `<use>` copies and icon-sprite symbols disappear, and multi-line text collapses into one line. Saving such a file then writes those losses back.

This spec closes the gaps that cause most of the visible damage and can be fixed without new types of object:

- **Style completeness**: fill rule, opacity (object, fill, stroke), stroke caps, joins, miter limit and dashes become part of a shape's style. They are rendered, editable, and stored in `.p2s` and SVG.
- **Rounded rectangles**: corner radii (`rx`/`ry`) on rectangles.
- **CSS styles**: `<style>` sheets with simple selectors are applied on import.
- **`<use>` and `<symbol>`**: expanded into independent copies on import.
- **Text lines**: `<tspan>` lines become separate text objects; text anchor (start/middle/end) is kept.
- **Import report**: whatever still can't be read (gradients, clip paths, masks, images, filters, …) is reported instead of disappearing silently.

Groups, gradients, clip paths/masks and images need new kinds of object and come in later specs. Fonts (family, weight, style) belong to the "Text round 2" work.

## Alignment with Product Vision

- **Target users**: "People leaving Illustrator … need reliable import/export", "Inkscape users … their SVG files carry over and back".
- **Success metric, Interop**: "common Inkscape and Illustrator-exported SVG files open correctly".
- **Principle 4**: "features SVG can't express degrade predictably … instead of silently disappearing". The same holds the other way round: SVG features PressToShape can't express yet are reported.
- **Pillar 2, Rich paint**: opacity is its first step.
- **Feature gap list, P1 "Style"**: opacity per object and per fill/stroke; stroke caps, joins, miter limit, dashes. **P1 "Shapes and tools"**: rounded rectangle corners. **P2 "Files"**: better SVG import (CSS styles, `<use>`).

## Requirements

### Requirement 1: Fill rule

**User Story:** As a designer opening icons and lettering from other programs, I want shapes with holes to keep their holes, so that the artwork looks as it was drawn.

#### Acceptance Criteria

1. Every shape's style SHALL have a fill rule, **nonzero** (default, as today) or **evenodd**.
2. The canvas, PNG export, hit-testing and bounds SHALL use the shape's fill rule: clicking inside an evenodd hole does not hit the shape's fill.
3. WHEN an SVG with `fill-rule` (attribute, inline style, CSS or inherited) is opened or pasted THEN the shape SHALL keep it; WHEN saved as SVG THEN `fill-rule="evenodd"` SHALL be written for evenodd shapes.
4. The selection panel SHALL let the user switch the fill rule of selected shapes (one undo step).
5. Booleans, divide and Composites SHALL treat each evenodd shape by its fill rule, so the result matches what was visible before.
6. Object to Path SHALL keep the fill rule.

### Requirement 2: Opacity

**User Story:** As an artist, I want transparent objects and semi-transparent fills and strokes, so that layered and translucent artwork imports and can be drawn.

#### Acceptance Criteria

1. Every shape's style SHALL have an **object opacity**, a **fill opacity** and a **stroke opacity**, each 0–100 % (default 100 %).
2. Object opacity SHALL apply to the shape as a whole: where its stroke overlaps its own fill, the result looks like one flattened object made transparent, as in SVG.
3. Fill and stroke opacity SHALL apply to that paint only.
4. WHEN an SVG is opened or pasted THEN `opacity`, `fill-opacity`, `stroke-opacity`, and alpha in colours (`rgba()`, `hsla()`, `#rrggbbaa`, `#rgba`) SHALL be read. A colour's alpha multiplies with its paint opacity.
5. WHEN a group (`<g>`) has an opacity below 100 % THEN that opacity SHALL be multiplied into each shape inside it. Because this differs from SVG where the group's shapes overlap, the import report SHALL say that group opacity was approximated.
6. WHEN saved as SVG THEN opacities below 100 % SHALL be written as `opacity`, `fill-opacity` and `stroke-opacity`.
7. The selection panel SHALL show an object opacity control for selected shapes, and fill and stroke opacity next to the fill and stroke colours. Changing them is one undo step; dragging a slider merges into one step.
8. Tool default styles SHALL include the opacities, so tools can draw semi-transparent shapes.
9. A shape with 0 % opacity SHALL still be selectable by clicking it, as in other editors.

### Requirement 3: Stroke options

**User Story:** As a designer, I want stroke caps, joins and dashes, so that lines from other programs look right and I can draw dashed and rounded lines myself.

#### Acceptance Criteria

1. Every shape's style SHALL have:
   - **cap**: butt (default), round, square;
   - **join**: miter (default), round, bevel;
   - **miter limit** (default 4);
   - **dash pattern**: a list of dash and gap lengths (default: none, a solid line) and a **dash offset**.
2. The canvas, PNG export, hit-testing and bounds SHALL use them (round and square caps extend the stroke beyond the end points).
3. WHEN an SVG is opened or pasted THEN `stroke-linecap`, `stroke-linejoin`, `stroke-miterlimit`, `stroke-dasharray` and `stroke-dashoffset` SHALL be read; an odd-length dash list is repeated, as in SVG. Dash lengths and offset scale with the shape's transform like the stroke width.
4. WHEN saved as SVG THEN non-default values SHALL be written.
5. The selection panel and tool options SHALL show cap, join (with miter limit when join is miter) and dashes for shapes and tools with a stroke. Dash lengths are entered in the document's unit.
6. Changing them SHALL be one undo step each.

### Requirement 4: Rounded rectangles

**User Story:** As a designer, I want rectangles with rounded corners, so that rounded rectangles from other files stay rectangles and I can make them myself.

#### Acceptance Criteria

1. Rectangles SHALL have corner radii `rx` and `ry` (default 0). The radii are clamped to half the width and half the height when drawn, as in SVG.
2. WHEN an SVG `<rect>` with `rx` and/or `ry` is opened or pasted THEN it SHALL stay a rectangle with those radii (one given value is used for both, as in SVG).
3. WHEN saved as SVG THEN non-zero radii SHALL be written as `rx`/`ry`.
4. The selection panel SHALL have a corner radius field for selected rectangles (one value for both radii; a rectangle with different `rx` and `ry` shows them as mixed and keeps them until the user enters a value), in the document's unit.
5. WHEN a rectangle is resized with handles or numeric fields THEN its radii SHALL stay the same (clamped when drawn).
6. Object to Path, booleans, divide and Composites SHALL use the rounded outline.
7. On-canvas corner radius handles and per-corner radii are out of scope.

### Requirement 5: CSS styles

**User Story:** As someone leaving Illustrator, I want files that style shapes through CSS classes to open with their colours, so that I don't have to recolour every shape by hand.

#### Acceptance Criteria

1. WHEN an SVG with `<style>` elements (anywhere in the document, including inside `<defs>`, plain or in CDATA) is opened or pasted THEN their rules SHALL be applied to matching elements.
2. Supported selectors: element type (`rect`), class (`.st0`), id (`#logo`), universal (`*`), compound selectors of these (`path.st0`, `.a.b`), and comma-separated selector lists.
3. Supported properties: every style property this spec reads (fill, stroke, stroke width and options, opacities, fill rule, font size, text anchor, display, visibility).
4. Precedence SHALL follow CSS: presentation attributes are weakest, then stylesheet rules by specificity and order, then inline `style`; `!important` stylesheet declarations beat normal inline ones.
5. Rules with selectors that aren't supported (descendant and child combinators, attribute selectors, pseudo-classes) and at-rules (`@media`, `@font-face`, …) SHALL be skipped without breaking the rest of the sheet, and the import report SHALL say that some CSS rules were not applied.
6. CSS comments SHALL be ignored.
7. Saving writes styles as presentation attributes, as today; the stylesheet itself is not kept.

### Requirement 6: `<use>` and `<symbol>`

**User Story:** As a designer, I want repeated elements and icon sprites to open with every copy, so that nothing is missing from the drawing.

#### Acceptance Criteria

1. WHEN an SVG with `<use>` is opened or pasted THEN each `<use>` SHALL become an independent copy of the referenced element (shape, group, or another `<use>`), placed by the `<use>`'s `x`, `y` and `transform`, with the `<use>`'s styles inherited by the copy as in SVG.
2. Both `href` and `xlink:href` SHALL be supported; references can point forward in the document and into `<defs>`.
3. WHEN a `<use>` references a `<symbol>` THEN the symbol's content SHALL be placed, scaled by its `viewBox` into the `<use>`'s `width`/`height` (with `preserveAspectRatio`'s default behaviour).
4. Elements inside `<defs>` and `<symbol>` SHALL appear only where they are used, never on their own.
5. Missing references and reference cycles SHALL be skipped and reported, never hang or crash the import. Deep nesting SHALL be bounded.
6. The copies are ordinary shapes: saving writes them as separate elements. Keeping `<use>` links is out of scope (symbols are a later feature).

### Requirement 7: Text lines and anchor

**User Story:** As a designer, I want multi-line and centred text from other programs to keep its lines and alignment, so that headings and labels stay where they were.

#### Acceptance Criteria

1. WHEN a `<text>` holds `<tspan>`s that start new positions (own `x`/`y`, or `dy` as Inkscape writes for lines) THEN each positioned run SHALL become its own text object at that position, with its own font size and paint where the tspan sets them.
2. Runs without their own position SHALL stay in the text object they continue.
3. Text objects SHALL have an **anchor**: start (default), middle, end. The canvas, export, hit-testing and bounds SHALL place the text by it, as SVG `text-anchor` does.
4. WHEN an SVG is opened or pasted THEN `text-anchor` SHALL be read; WHEN saved THEN a non-default anchor SHALL be written.
5. The selection panel SHALL let the user change the anchor of selected text objects, keeping the anchor point in place (the text moves around it).
6. Mixed styles inside one line (a bold word, a coloured word) are out of scope: the line takes the style of its text element, and the import report notes it. Font family, weight and style are out of scope.

### Requirement 8: Import report

**User Story:** As a user opening a file from another program, I want to know what couldn't be imported, so that I don't save over a file and lose parts of it without noticing.

#### Acceptance Criteria

1. Opening or pasting an SVG SHALL collect notes about everything that wasn't imported or was approximated, each note once with a count where useful (e.g. "3 gradients shown as grey"). At least:
   - gradients and patterns (painted grey, as today);
   - clip paths and masks (content shown unclipped);
   - images; filters; markers;
   - group opacity approximated; CSS rules not applied; missing or cyclic `<use>` references;
   - mixed text styles in one line; nested `<svg>` elements; other unknown elements.
2. WHEN a document is opened with notes THEN the user SHALL see them in a dialog listing every note (not only in the status bar), with a short hint that saving as SVG writes the file without those parts. WHEN nothing was lost THEN no dialog SHALL appear.
3. WHEN pasting with notes THEN the notes SHALL appear in the status bar message, as today.
4. Elements PressToShape writes itself (layers, Composite metadata, `sodipodi:namedview`, `<metadata>`, `<title>`, `<desc>`) SHALL NOT produce notes.

### Requirement 9: Native format and round trips

**User Story:** As a user, I want my files to keep every new style setting, so that nothing changes when I save and reopen.

#### Acceptance Criteria

1. `.p2s` SHALL store the new style fields, rectangle radii and text anchor. This is a new format version with a migration from the previous one (old files open with the defaults), a sample file and a `docs/file-format.md` row.
2. Tool default styles in `.p2s` SHALL include the new fields.
3. Every new property SHALL round-trip through `.p2s` exactly and through SVG within number formatting; PressToShape SVG opened in Inkscape SHALL show them the same way.
4. Clipboard copy/paste inside PressToShape and to/from other apps SHALL keep them.
5. Undo/redo SHALL restore every change.

### Requirement 10: Real-world test files

**User Story:** As a developer, I want test files that look like real exports, so that regressions in import show up in tests.

#### Acceptance Criteria

1. The test suite SHALL have small SVG fixtures written in the style of Illustrator (CSS classes, `<style>` in `<defs>`), Inkscape (layers, `sodipodi`, tspan lines with `dy`), Figma (clip paths around frames, `fill-rule`, `rgba`), and an icon sprite (`<symbol>` + `<use>`). They are hand-written for the tests, not copied from third-party files.
2. Tests SHALL check shape count, types, styles and positions after import, and the notes produced.

## Non-Functional Requirements

### Code Architecture and Modularity
- The new style fields live in `models/shapes.Style` (and `RectShape`, `TextShape`), frozen as today. Defaults equal today's behaviour, so existing code and files are unaffected.
- CSS parsing and selector matching are a separate Qt-free module under `formats/`, unit-tested on its own; `<use>` expansion stays inside the SVG reader. No new runtime dependency unless the design shows a clear need.
- Paint setup for new style fields stays in `render/paths.py` (one place), so canvas, export and hit-testing agree.
- Edits go through operations in `editing/operations/` with undo labels; views only show and forward values.

### Performance
- Shapes at 100 % opacity SHALL render exactly as fast as today (no extra layer). Opacity layers are only used where needed.
- Opening a large SVG (10,000 shapes, a stylesheet with a few hundred rules) SHALL not take noticeably longer than today (target: under 2× today's parse time).

### Reliability
- Foreign SVG must never crash the import: malformed CSS, bad lengths, cycles and unknown values fall back to defaults and, where content is lost, produce a note.
- Old `.p2s` files keep opening.

### Usability
- New controls follow the existing panels: shown only when they apply (rectangle radius for rectangles, anchor for text, stroke options when a stroke is on), compact enough not to crowd the panel.
- All new UI text is translated (English source + German).
- No new keyboard shortcuts.
