# Requirements Document

## Introduction

Level 4 of the SVG conformance roadmap: **clipping and masking**, built as a real, non-destructive editor feature. Today `clip-path` and `mask` are dropped on import (`Note.CLIP`, `Note.MASK`: "its content is shown unclipped"), nothing is written back, and the editor has no way to crop an object with another one. In the W3C suite the `masking` chapter matches 3 of 19 tests.

This level adds **clipping masks** (Illustrator's "Make Clipping Mask") and **opacity masks** (luminance masks):

- **Model**: a new container shape, `MaskGroup`, holds the **mask objects** and the **content** separately. The mask stays a live, editable object (enter the container, move/edit/restyle the mask shapes, release to get everything back). Nothing is baked or boolean-cut.
- **Two mask types**: `clip` (the union of the mask objects' geometry; paint ignored, `clip-rule` honoured) and `luminance` (the mask objects are rendered like normal artwork and their luminance × alpha becomes the content's alpha, as SVG `<mask>`).
- **Reader**: `<clipPath>` (`clipPathUnits`, `clip-rule`, `transform`, children shapes/text/`<use>`, nested `clip-path` on the clipPath and on its children) and `<mask>` (`maskUnits`, `maskContentUnits`, `x y width height`, children as artwork). A `clip-path` / `mask` on any element becomes a `MaskGroup` around it.
- **Render**: Skia `clipPath` (anti-aliased) and a `saveLayer` with a luminance colour filter. Only masked content pays for a layer.
- **Save**: SVG writes `<clipPath>` / `<mask>` in `<defs>` and `clip-path="url(#id)"` / `mask="url(#id)"` on a `<g>`; `.p2s` stores the container (version bump + migration + sample); the clipboard carries it.
- **Editor**: Object → Clipping Mask → Make / Release, Opacity Mask → Make / Release (and invert for luminance), enter the container to edit mask and content, Layers panel shows the mask objects marked as such.

Decisions taken before writing (2026-10-23):

- **Non-destructive, one container, no per-shape fields.** `clip`/`mask` could be optional fields on every shape type; they are one container instead, like `GroupShape` and `CompositeShape` (rule: `children_of`, `edit_path`, `containers.py`). Reasons: one place to teach hit-testing, bounds, rendering, the Layers tree and the writer; group-level masks are the common case in real files; a mask shared by several objects in SVG means "mask the group", which is what the container is.
- **Mask objects are ordinary shapes** inside the container, flagged by position (they live in `MaskGroup.mask`, content in `MaskGroup.content`), not by a flag on the shape. Selecting, moving, node-editing, booleans-ing a mask shape work as for any shape inside a container.
- **Clip geometry = fill geometry.** Strokes, fill paint, opacity and `visibility` of clip children are ignored (SVG: `masking-intro-01-f`); `clip-rule` comes from the child. Masks use the full rendering of their children, strokes included.
- **Mask coordinates stay resolved to user space of the container.** The reader converts `objectBoundingBox` units of clip/mask into the content's user space using the element's bounding box at import time (a bake-in of the *mask objects* only), because the editor edits mask shapes as real shapes. Moving the container moves content and mask together. Documented difference: a mask object that was in bounding-box units no longer follows when the content's size changes through editing the content alone. (The gradient level kept bounding-box units unresolved for gradient-follows-shape; masks are objects, not paint.)
- **`mask` luminance only.** `mask-type: alpha` and `mask-mode` (SVG 2 / CSS Masking) are read when present and mapped to a second mask type `alpha`, since Skia gives it for free; `color-interpolation: linearRGB` on a mask is read and noted (sRGB used), as in Level 3.
- **Mask `x y width height` region** (default -10% / 120% of the content's bounding box) is kept as an explicit clip rect of the mask layer when it cuts something; otherwise omitted. Design decides if it is a model field or a baked extra rectangle.
- **Release is not undo of Make**: Release dissolves the container into its content (mask objects are deleted for clipping masks and offered back for opacity masks, see Requirement 5.4); both are normal one-step undoable operations.
- **No `clip` property (CSS clip), no `<switch>`, no markers/filters.** Filters are the next level.

Out of scope here: the legacy `clip` property on viewports, `mask-image`/`mask-border`/`mask-composite` (CSS Masking), clip-path basic shapes (`circle()`, `polygon()`; read as unsupported with a note), masks on `<svg>` roots other than what nested svg handling already does, soft-edge/feather UI (needs filters), creating masks from Text outlines in the UI (text may be a mask object, no extra command).

## Alignment with Product Vision

- **Product Principle 3, non-destructive by default**: clipping masks and opacity masks are the classic non-destructive illustration tools; the editor gets them as editable containers.
- **Success metric, Interop**: clip paths and masks are in most Inkscape and Illustrator exports (crop frames, vignettes, text knockouts); today they silently show unclipped content, often wrong by a large margin.
- **Principle 4**: nothing SVG expresses is silently dropped any more; what stays unsupported (basic-shape clip, `mask-image`) is reported.
- **Principle 5, Inkscape interop**: written as `<clipPath>`/`<mask>` on `<g>`, which Inkscape reads as "clip"/"mask" and shows as such.
- **Core pillar 3, non-destructive effects**: the masking layer mechanism is the base the blur/shadow level builds on.
- **Principle 6, WYSIWYG**: canvas, PNG export and the saved SVG (checked against resvg) match.

## Requirements

### Requirement 1: Mask container in the model

**User Story:** As a user, I want to crop an object with another object and still be able to change either one later.

#### Acceptance Criteria

1. `models/shapes.py` SHALL define a frozen `MaskGroup` with `id`, `mask` (tuple of shapes), `content` (tuple of shapes), `mask_type` (`clip` | `luminance` | `alpha`), `inverted` (bool), `transform` (identity, like `GroupShape`), `hidden`, `locked`, plus an optional `region` (design: rect or none) for the SVG mask region. It has no style of its own.
2. `Shape` and `ContainerShape` SHALL include `MaskGroup`; `children_of` SHALL return `mask + content` in a defined order (design decides; the mask objects are reachable as part of the container so `edit_path`, selection, delete, move and the Layers tree work), and a way to tell which side a child is on SHALL exist as a helper (`is_mask_part(container, child_id)`).
3. Code that reads `shape.style` or recurses into shapes SHALL handle `MaskGroup` together with groups (rule: "handle groups first"): drawing, hit-testing, bounds, `restyle_shape`, transforms, encoders, clipboard, SVG writer, booleans/composite inputs, align, snapping targets. `tests/` SHALL include a grep-style guard or a table test listing every `match shape` on shape types so a new container cannot be missed.
4. `models.shapes.sanitized` SHALL keep `mask_type` in its enum, make an empty `mask` valid (clip: content invisible; luminance: content invisible, as SVG `masking-mask-02-f`) and never raise on non-finite region numbers.
5. Nesting SHALL work: a `MaskGroup` may hold `MaskGroup` in content and in mask (SVG: a clipPath with a `clip-path`, a masked element inside a mask).
6. Tests: construction, sanitising, equality, `children_of` order, `is_mask_part`.

### Requirement 2: Reading clip paths and masks

**User Story:** As a user opening an SVG with clip paths and masks, I want them to stay clip paths and masks.

#### Acceptance Criteria

1. `clip-path: url(#id)` and `mask: url(#id)` (attribute, `style`, CSS) on any drawn element (shape, `<g>`, `<use>`, `<text>`, nested `<svg>`, `<a>`) SHALL wrap that element in a `MaskGroup`. An element with both gets two nested containers (`clip` outside, `mask` inside); the result is the same in either order, the design fixes one.
2. `<clipPath>`: `clipPathUnits` (default `userSpaceOnUse`; `objectBoundingBox` resolved as in the decisions), `transform` on the clipPath element, children `rect circle ellipse line polyline polygon path text use`, with `clip-rule` per child; a child's own `clip-path` SHALL clip that child only; a `clip-path` on the `<clipPath>` element SHALL intersect (nested `MaskGroup`); children that are not shapes or whose `display` is `none` contribute nothing; `visibility` is ignored (spec rule).
3. `<mask>`: `maskUnits` (default `objectBoundingBox`), `maskContentUnits` (default `userSpaceOnUse`), `x y width height`, children read exactly like normal artwork (groups, gradients, text, strokes, opacity, nested masks), `mask-type`, `color-interpolation` noted.
4. The reference SHALL resolve through the same id map as `<use>` and gradients; the clip/mask element and ancestors with `display: none` SHALL work (SVG rule). The clipPath and its children SHALL NOT inherit clipping from the clipPath's ancestors (`masking-path-14-f`).
5. Invalid and degenerate cases: reference to a missing id → the element is drawn unclipped/unmasked (SVG 1.1 says error; browsers ignore the property; document as chosen) and a note is added; reference to a non-clipPath / non-mask element → same; cycles (a clipPath referencing itself or through children) and depth > design cap → treated as invalid reference, never an exception; a clipPath with no valid child → content fully clipped; mask with no children → content invisible; `objectBoundingBox` units on content with an empty bounding box (a horizontal line) → element not rendered (SVG rule).
6. Several elements referencing one clipPath/mask SHALL each get their own copy of the mask objects (frozen shapes shared structurally, new ids per use); resolution is memoised per id.
7. `Note.CLIP` / `Note.MASK` SHALL NOT be raised for what is now supported; new notes (counted, translated): "{count} clip path with a basic shape was ignored", "colours in a mask are interpolated in sRGB" (the `linearRGB` case), "{count} reference to a missing clip path or mask was ignored".
8. Clip/mask reading SHALL not change where `<clipPath>` / `<mask>` content is rendered: those elements are definitions, never drawn where they stand (already in `_NOT_RENDERED`).
9. Hostile input (10 000 clip children, cycles, NaN, nesting 100 deep) SHALL never raise out of the reader or produce non-finite values; caps and the note for exceeded caps are defined by the design.
10. Tests: all `masking-path-*`, `masking-mask-*`, `masking-intro-01-f`, `struct-use-*` cases that use `clip-path`, `painting-*` ones that use `mask`, plus unit tests for every rule above.

### Requirement 3: Rendering

**User Story:** As a user, I want clips and masks to look right on the canvas and in exported PNG, at any zoom, without slowing the canvas down.

#### Acceptance Criteria

1. `render/` SHALL draw a clip `MaskGroup` as: save, `clipPath` of the union of the mask objects' outlines (`transforms.area_outline`-style handling for fill-rule: nonzero/evenodd per child, combined with pathops union when more than one child; anti-aliased), content, restore. `inverted` clips outside instead.
2. A luminance mask `MaskGroup` SHALL draw: `saveLayer` for the content, then the mask objects in a second layer composited with `kDstIn` through a colour filter that maps RGB to luminance (SVG coefficients) × alpha; `alpha` type uses alpha directly; `inverted` inverts the mask value. The mask `region` clips the mask layer.
3. Content without any mask SHALL cost nothing extra; masked content SHALL cost one clip (clip type) or two layers (mask types) per container, and only where the container is inside the visible area.
4. The clip path geometry of a `MaskGroup` SHALL be cached with the shape's cached path (`PathCache` keyed by shape id; rebuilt when the frozen shape changes) so panning and zooming build no clip paths per frame; gestures that move shapes through `Overlay.matrix` SHALL keep the recorded picture.
5. Gradients, text, groups, nested masks and strokes inside mask objects SHALL render (luminance masks use the full artwork look).
6. `objectBoundingBox`-unit masks resolved at import (decisions) need no render support; the renderer only sees user-space geometry.
7. Hit-testing a `MaskGroup` SHALL only hit where content is visible: not outside a clip; inside a luminance mask where the mask value is > 0 is approximated by the mask objects' fill outlines (documented approximation, design decides). Bounds of a clip `MaskGroup` SHALL be the intersection of content bounds and clip bounds; luminance: content bounds.
8. Opacity layers keep the existing rule (a layer only where required); a `MaskGroup` inside a group with opacity SHALL composite correctly.
9. PNG export SHALL use the same path (`render/export.py` through `render/scene.py`); no separate masking implementation.
10. Tests: CPU-surface pixel assertions for clip (nonzero, evenodd, nested, transformed, union of two children, inverted), luminance mask (white, black, gradient, 50% alpha, stroke in mask, region cut), alpha mask, empty mask/clip, mask on group with opacity; a benchmark note (`scripts/bench_canvas.py`, 1000 masked objects) in the task log with the cost recorded.

### Requirement 4: Saving and round trips

**User Story:** As a user, I want clips and masks to survive save and reopen in PressToShape and in other programs.

#### Acceptance Criteria

1. Saved SVG SHALL write a clip `MaskGroup` as `<g clip-path="url(#id)">content</g>` with `<clipPath id>` (mask objects as children, `clip-rule` on each, `clipPathUnits=userSpaceOnUse`) in `<defs>`, and a mask `MaskGroup` as `<g mask="url(#id)">` with `<mask id>` (`maskUnits=userSpaceOnUse`, `x y width height` from the region or a safe default covering the mask bounds, `mask-type` for `alpha`). Ids SHALL be generated, unique and stable between saves of the same document; `inverted` SHALL be written as the inversion in SVG terms (clip: an enclosing rect plus the objects with evenodd; mask: a `feColorMatrix`-free form, design chooses and tests in resvg).
2. A `MaskGroup` whose content is a single shape MAY be written with the attributes on that element when no information is lost; otherwise a `<g>` is written. Design decides; round trip must reproduce an equal model either way.
3. The written file SHALL render the same in resvg as on our canvas for each case in Requirement 3.10 (existing generator check, `tests/formats/test_svg_generator.py`).
4. `.p2s` SHALL store `MaskGroup` with explicit encoders and decoders (no generic dataclass walk); `CURRENT_VERSION` SHALL be bumped with a migration from the previous version, a `tests/formats/samples/v<N>.p2s` sample and a row in `docs/file-format.md`. Older files SHALL open unchanged.
5. The clipboard payload SHALL carry `MaskGroup`; copying only mask objects out of an entered container pastes them as plain shapes.
6. A document opened from SVG, saved as `.p2s`, reopened and saved as SVG SHALL produce an equivalent mask structure (type, mask objects, content, region).
7. Inkscape interop: the saved `<clipPath>` / `<mask>` SHALL be read back by Inkscape as clip / mask of the group (checked by reading the structure Inkscape writes itself; no Inkscape code is copied, only the format facts).
8. Tests: SVG round trip for clip, nested clip, evenodd, luminance, alpha, inverted, region; p2s round trip and migration from the previous sample; clipboard round trip; dedup of equal `<clipPath>` content written for several shapes is **not** required (each container writes its own).

### Requirement 5: Editor operations

**User Story:** As an illustrator, I want to make and release clipping and opacity masks from the Object menu and keep working on both parts.

#### Acceptance Criteria

1. Registered operations SHALL exist, with menu entries under Object → Clipping Mask and Object → Opacity Mask, no default shortcut for opacity masks (rarely used); `object.clip.make` MAY get a shortcut (Illustrator's Ctrl+7) if the user wants it, otherwise menu only (design asks, per the rule on shortcuts):
   - `Make Clipping Mask`: the topmost selected object is the mask, all other selected objects become the content; needs at least two selected objects in one container; result replaces them at the position of the topmost object and is selected.
   - `Release Clipping Mask`: dissolves the selected clip `MaskGroup`; mask objects stay as ordinary shapes (unstyled clip objects get a visible default style: no fill, thin stroke, as Illustrator, so they are not lost invisibly).
   - `Make Opacity Mask` / `Release Opacity Mask`: same for luminance; releasing keeps the mask objects as ordinary shapes above the content, hidden.
   - `Invert Mask` toggles `inverted` on the selected mask container.
   - `Mask Type` (luminance / alpha) is a Layers-panel/context choice of the selected opacity mask.
2. Make works on a mixed selection of shapes, groups, composites and other mask containers; objects in different containers or layers SHALL be refused with a status message; locked or hidden objects SHALL be handled by the existing selection rules.
3. A selected object that is already a `MaskGroup` and a second selected object SHALL be maskable again (nesting is not flattened).
4. Entering a `MaskGroup` (double-click, as groups) SHALL show mask objects and content together with the mask objects drawn with a marker overlay (dashed outline in the theme colour); a toolbar/context action "Edit Mask / Edit Content" MAY isolate which side is editable (design decides; at minimum, both are editable in the entered state and the Layers panel tells them apart).
5. Operations SHALL go through `editing/containers.py` (`pickable_shapes`, `change_container`) and be one undo step each with a named label (translated); enter/leave are not undo steps.
6. Deleting all mask objects or all content while inside SHALL release the container (as an empty entered container is removed today). Deleting the container deletes both.
7. Copy/cut/paste/duplicate/Alt+drag duplicate, group/ungroup, arrange (z-order), align, flip, transform handles and boolean operations SHALL treat a `MaskGroup` as one object (its bounds are the visible bounds).
8. Style editor: with a `MaskGroup` selected, the style panel SHALL edit nothing destructive (like `GroupShape`: opacity only, `restyle_shape` recurses into content only, never mask objects), and says so by disabling the fields the container has no meaning for.
9. Layers panel: a `MaskGroup` row shows a clip/mask icon; its two sides appear as two sub-rows ("Mask", "Content") or marked children (design decides); drag/drop between sides is not required.
10. Tests: every operation (positive cases and each refusal), undo/redo labels, status messages, selection after the operation, interaction with `edit_path`.

### Requirement 6: Updated baseline

**User Story:** As the maintainer, I want the conformance numbers updated with this level.

#### Acceptance Criteria

1. Every `masking-*` test that matches SHALL be on the pass list after a check by eye; mismatches stay as `!name # reason`. `!masking-path-12-f` SHALL be re-evaluated. Tests that are filter-related (`masking-filter-01-f`) keep an explicit reason (filters level).
2. `docs/svg-conformance.md` SHALL be regenerated, `.spec-workflow/steering/product.md` / `tech.md` import-gap lines updated (clip paths and masks removed from "skipped or approximated"), the feature gap list's Level 4 items ticked.
3. Struct and painting tests that were failing only because of ignored `clip-path`/`mask` SHALL be re-run; those that now match are added after a check by eye.
4. No test on the pass list before this level SHALL leave it.
5. Target: at least 15 of 19 `masking` tests match; the rest have a documented reason.

## Non-Functional Requirements

### Code Architecture and Modularity
- Reader code in its own module (`formats/svg_masks.py`: reference resolution, units, clip-rule, nesting limits, error rules; pure and testable without the reader). Writer code in `formats/svg_mask_writer.py` (or the module the design picks) rather than growing `svg.py`. Render code in `render/masks.py`. Operations in `editing/operations/masks.py`. Models only get the frozen value type.
- No Qt below `views/`. Import direction rules stay (`tests/test_architecture.py`). The only view additions are menu/keymap entries, the Layers panel rows and the entered-mask overlay colours (`CanvasColors`).
- p2s encoders/decoders explicit; operations plain functions `operation(session, ...)`; shapes frozen; `dataclasses.replace` for changes.

### Performance
- Documents without masks draw and open as fast as today. Per-frame cost of masked content: one cached clip path (clip) or two layers (mask), no clip geometry rebuilt per frame; recorded pictures reused while a gesture moves other objects.
- Clip/mask references are resolved once per id on import; 10 000 elements sharing one clipPath open in similar time to the same file without it plus the copy cost of the mask objects.

### Security
- Reference cycles and nesting have depth limits and cycle detection; child counts are capped; no value from a file reaches Skia unsanitised (non-finite, huge or degenerate numbers are replaced before the clip path or layer is built).

### Reliability
- Every SVG that opens today still opens. A bad clip or mask never prevents the rest of the file from opening and never crashes the canvas; it degrades as Requirement 2.5 says.
- Everything the app can save reopens (tested round trips); older `.p2s` files migrate.

### Usability
- Make/Release are discoverable in the Object menu with clear, translated labels; refusals say why in the status bar. Notes are short and counted. Translations (`de.po`) complete, `uv run python scripts/update_translations.py` run; mnemonics do not clash.
