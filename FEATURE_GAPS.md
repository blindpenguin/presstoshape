# Feature gaps and SVG conformance

For information: where PressToShape stands and what is still missing. Two tracks in one list:

- **Editor features** compared with Inkscape, Illustrator and Affinity Designer (as of 2026-10-18, updated 2026-10-20).
- **SVG conformance** measured against the W3C SVG 1.1 (Second Edition) test suite (2026-10-21).

Many items belong to both tracks: gradients are a paint feature and SVG levels at the same time. Those live in the conformance levels below and the editor lists point there. Each level and each larger editor item is meant to become one spec, written when we get to it.

Editor priorities:

- **P1**: basics people expect in the first five minutes; their absence feels broken.
- **P2**: core professional depth; needed for real projects.
- **P3**: advanced, or a later differentiator.

PressToShape today (2026-10-21): align/distribute, rulers, guides, grid, snapping, groups (with opacity), select / node / pen / pencil / rectangle (rounded corners) / ellipse / text (left/centre/right alignment) tools, transform handles, fill + stroke + width, opacity (object, fill, stroke), fill rule, line caps/joins/dashes, layers, object hide/lock + layer tree, booleans + divide, Composites, raise/lower, undo, clipboard (copy/cut/paste/paste in place/duplicate, Alt+drag), native `.p2s` + SVG open/save (CSS styles, `<use>`/`<symbol>`, tspan lines, import notes dialog), PNG export with DPI, crash recovery + backup on save, New Document dialog with presets, units (px/mm/cm/in/pt) and DPI, recent files, Settings window, English + German UI with user translations, nightlies.

## SVG conformance

### Target

The SVG spec defines conformance classes. What they mean for us:

- **Conforming SVG generator** (saving): every file we write is a conforming SVG document and looks the same in other viewers as on our canvas. Fully reachable; goal for every level.
- **Conforming SVG interpreter** (opening): any valid SVG opens without error; whatever we can't represent is reported (import notes), never silently dropped or crashing. Already almost true.
- **Static rendering fidelity**: the static subset of SVG 1.1 opens looking like the reference. This is what the levels below climb, one feature area at a time.
- **Conforming SVG viewer** (animation, scripting, DOM, interactivity, SVG fonts): non-goal. An editor works on static drawings; Inkscape and Illustrator don't claim it either.

### Baseline 2026-10-21

Suite: `https://www.w3.org/Graphics/SVG/Test/20110816/archives/W3C_SVG_11_TestSuite.tar.gz` (525 tests with reference PNGs, W3C test suite licence / BSD-3). Probe scripts were scratch only; Level 0 turns them into a tool.

- **Parsing**: 524/525 open without error; all 524 survive save → reopen. The one crash: `paths-data-20-f` (bad arc flag; the spec says render the path up to the error).
- **Rendering**: our PNG export vs. reference PNG (both on white, 3 px blur, pixels differing > 60): 269/525 within 3 %. The metric is rough:
  - Animation/DOM/script tests "pass" when their static first frame happens to match; meaningless for us.
  - Some reference PNGs are older than their test (`styling-pres-03-f`: reference blank, our green rect is correct for the current test).
  - Font differences (our sans-serif vs. the suite's SVG fonts) cost a few %, so text-heavy tests fail on glyph shapes alone.
  - So the pass list must be curated by eye once, then used as a regression check.

Per area (tests / matching within 3 %), with the level that addresses it:

| Area | Tests | Match | Missing | Level |
|---|---|---|---|---|
| shapes, paths, painting-stroke, coords-trans | 70 | 68 | path error handling | 1 |
| painting-fill, color-prop | 10 | 6 | `currentColor`, `color` property, CSS2 system colours | 1 |
| styling (CSS, presentation attributes) | 18 | 8 | complex selectors, specificity, `!important` | 1 |
| struct-cond (`<switch>`) | 7 | 2 | conditional processing: only the first matching child | 1 |
| text-ws | 3 | 0 | `xml:space`, whitespace rules | 1 |
| coords-viewattr, struct-svg, struct-frag | 13 | 7 | nested `<svg>`, `preserveAspectRatio` | 2 |
| pservers, styling-inherit, painting-render | 36 | 4 | gradients, patterns | 3 |
| masking | 19 | 14 | images and patterns inside masks, nested `<svg>` overflow clip (Level 4 done 2026-10-23; 12 on the pass list, 2 script-driven) | 4 |
| struct-image, struct-symbol, external `<use>` | 20+ | 4 | images, references into other files | 5 |
| painting-marker | 8 | 4 | markers | 6 |
| text (without ws, dom) | 54 | 30 | per-tspan styles, fonts, spacing, `textPath`, shaping (Arabic) | 7 |
| filters | 43 | 3 | filter effects | 8 |
| animate, script, interact, svgdom, *-dom, fonts, altGlyph, color-prof, extend | ~160 | n/a | non-goal | — |

Level 1 resolved `types-basic-02-f`: ours draws no red (correct per CSS), the suite image and resvg disagree (reviewed exception). Still unclear: `struct-use-06-b` (external references, probably Level 5).

Found while curating the pass list (small shapes the score misses): `coords-units-02-b` (percentage coordinates/lengths), `styling-elem-01-b` (`<style>` with unknown type applied), `struct-group-03-t` (first cell black). Root `width="100%"` without viewBox opens as a 100×100 page (`struct-frag-01-t`, Level 2).

### Levels

Every level has the same definition of done:

- The level's tests are in the curated pass list and match by eye and by metric.
- What the level reads is kept on save: `.p2s` round trip and SVG round trip.
- Saved SVG of those tests renders the same in a second renderer (resvg or rsvg-convert) as on our canvas (generator check).
- What still can't be represented produces an import note.

**Level 0 — Measure** (done 2026-10-21, spec `svg-conformance-harness`; numbers in `docs/svg-conformance.md`):
- [x] Script `scripts/svg_conformance.py`: downloads the pinned suite (SHA-256, like `build_package.py`), renders every test, writes a report per chapter (match %, notes, side-by-side sheet of failures).
- [x] Curated pass list checked in (116 tests, 43 reviewed-but-wrong with reasons); pytest fails when a listed test regresses, skips when the suite isn't fetched.
- [x] Generator check: saved SVG rendered by resvg (`resvg_py`) vs. our canvas, for built documents and every pass-list test.
- [ ] Optional later: resvg's test suite (MIT, ~1600 finer tests) as a second corpus.

**Level 1 — Correct what we already read** (no new object types):
- [x] Path data error handling: keep the path up to the first error (`paths-data-20-f`, `paths-data-18-f`); same for other attribute parse errors (shape not rendered, no crash).
- [x] `currentColor` and the `color` property, inherited (`painting-fill-02-t`, `color-prop-*`). Done in Level 1 spec; system colours (`color-prop-04-t`) are ignored as invalid, not mapped (reviewed exception); `color-prop-05-t` differs on purpose (SVG 2 behaviour, as resvg).
- [x] CSS: descendant, child, sibling, attribute, universal, `:first-child` selectors; specificity order; `!important` (`styling-css-04..10`). Unsupported selectors keep the note.
- [x] `<switch>`: only the first child whose `systemLanguage` / `requiredFeatures` / `requiredExtensions` match (`struct-cond-*`).
- [x] Text whitespace: default collapsing and `xml:space="preserve"` on read (`text-ws-*`); write `xml:space="preserve"` when a text has leading, trailing or double spaces.
- [ ] Generator: well-formed output, values in SVG grammar, `version`/namespace declarations checked by test.

**Level 2 — Viewports** (done 2026-10-22, spec `svg-conformance-level2`; overflow clip still open):
- [x] Nested `<svg>`: flattened into a group with the viewport transform (x, y, width, height, viewBox) instead of left out (`struct-group-02-b`, `struct-svg-03-f`, `styling-css-08-f`). Done in Level 2 spec; `struct-svg-01/02-f` are script-driven (reviewed exceptions).
- [x] `preserveAspectRatio` (all align values, meet/slice) on root, nested `<svg>` and `<symbol>` (`coords-viewattr-03-b`, `struct-use-09-b` via resvg). Root with absolute width/height of other proportions keeps its size. `<image>` cases (`coords-viewattr-02-b`, `-04-f`) wait for Level 5.
- [ ] Overflow clipping of nested viewports noted until Level 4, then done there.

**Level 3 — Paint servers** (also editor P2 "Gradients"):
- [x] (done 2026-10-22, spec `svg-conformance-level3`) Linear and radial gradients as paint: model, render, save, `.p2s`; `gradientUnits`, `gradientTransform`, `spreadMethod`, `href` inheritance between gradients, focal point (`pservers-grad-*`).
- [ ] On-canvas gradient editing (editor side; the style panel already shows and keeps gradients, see spec `svg-conformance-level3`).
- [ ] Patterns (`pservers-pattern-*`); maybe a later spec of its own.
- [x] `color-interpolation` (linearRGB) read and noted, sRGB used (`painting-render-01-b`); real linearRGB rendering is not implemented.

**Level 4 — Clipping and masking** (done 2026-10-23, spec `svg-conformance-level4`; also editor P2 "Clipping masks and opacity masks"):
- [x] Clip paths (`clipPathUnits`, clip-rule, nested clips, clip on groups, text and `<use>` in clips) and masks (luminance and alpha, `maskUnits`, `maskContentUnits`, region) as editable objects: a group with mask objects and content. Make/release clipping mask and opacity mask, invert, mask type, move between mask and content; `.p2s` version 9; saved as `<clipPath>` / `<mask>` (`masking-*`).
- [ ] Nested viewport overflow clip from Level 2 (`masking-path-03-b`): still open, nested `<svg>` content is shown unclipped and noted.
- [ ] Masks and clips with images or patterns inside wait for Levels 5 and the pattern spec (`masking-path-04-b`, `-06-b`, `-07-b`, `-11-b`).
- [ ] Inverted opacity masks are kept in `.p2s` but saved to SVG without the inversion until filters exist (Level 8).
- [ ] Keyboard shortcuts for Make/Release Clipping Mask (Illustrator: Ctrl+7) are not bound; ask before adding.

**Level 5 — Images and external references** (also editor P1 "Import images"):
- [ ] `<image>` embedded (data URI) and linked (relative path), PNG/JPEG, `preserveAspectRatio`; place images in the editor (`struct-image-*`, `struct-symbol-01-b`).
- [ ] `<use>` pointing into other files relative to the opened file (`struct-use-06-b`, `struct-use-05-b` partly).

**Level 6 — Markers** (also editor P1 "arrowheads"):
- [ ] `marker-start/mid/end`, `orient`, `markerUnits`, `refX/refY`, viewBox; arrowhead presets in the stroke options (`painting-marker-*`).

**Level 7 — Text** (also editor P2 "Text"):
- [ ] Per-tspan style (rich text) instead of one style per line (`text-text-*`, `text-tspan-*`); removes the "mixed styles" note.
- [ ] Font family, weight, style read, rendered and written (today always `sans-serif` on save); font picker.
- [ ] `letter-spacing`, `word-spacing`, `text-decoration`, `baseline-shift`, rotate per glyph (`text-spacing-*`, `text-align-*`).
- [ ] `textPath` (`text-path-*`); text on path in the editor.
- [ ] Complex shaping and bidi (Arabic, Hebrew) through Skia's shaper if skia-python exposes it (`text-intro-*`).

**Level 8 — Filters** (also editor P2 "Effects"):
- [ ] First the ones artists use: Gaussian blur, offset, flood, merge, composite → drop shadow, blur, glow (`filters-gauss-*`, `filters-offset-*`, `filters-composite-*`).
- [ ] Then colour matrix, blend, morphology, turbulence, lighting, as far as Skia's image filters cover them.

**Non-goals**: animation (SMIL), scripting and DOM, interactivity and events, SVG fonts and `altGlyph`, colour profiles, `foreignObject`. Files using them open with notes, static content intact.

## Editor features: P1, basics that are missing

### Editing
- [x] **Copy / Cut / Paste / Duplicate** (Ctrl+C/X/V/D), paste in place, paste between documents and to/from other apps (SVG on the clipboard).
- [x] **Groups**: group/ungroup (Ctrl+G / Ctrl+Shift+G), enter a group to edit, group opacity, SVG `<g>` in and out.
- [x] **Arrow-key nudge** (plain = small step in the document unit, Shift = ten, Alt = one screen pixel; Node tool nudges nodes). Configurable step still open ("More settings").
- [x] **Flip** horizontal/vertical (Shift+H / Shift+V). Text can't be mirrored, only its position.
- [x] **Lock and hide individual objects**, not only layers: Object → Hide Selection / Show All / Lock Selection / Unlock All (Ctrl+3 / Ctrl+Alt+3 / Ctrl+2 / Ctrl+Alt+2), eye and lock in the Layers panel tree, saved in .p2s and SVG (`display:none`, `sodipodi:insensitive`).
- [ ] **Select same** (fill, stroke, type), invert selection. (Deselect with Esc and Select All exist.)
- [ ] **Alt+click to select below**: cycle through stacked objects.

### Shapes and tools
- [ ] **Line tool**, polygon and star tool. (Rounded rectangle corners done, one radius for all corners; per-corner radii and on-canvas corner handles still open.)
- [x] **Pencil / freehand tool** with smoothing (F). Base for tablet pressure and brushes.
- [ ] **Eyedropper**: pick fill/stroke from a shape (and color from the canvas).
- [ ] **Zoom tool and hand tool**, Space+drag to pan from any tool.

### Style
- [x] **Opacity** per object and per fill/stroke.
- [x] **Stroke options**: caps, joins, miter limit, dashes, dash offset. Still open: alignment (inside/center/outside); arrowheads → SVG Level 6.
- [ ] **Color picker**: proper HSV/HSL/hex panel docked in the UI, recent colors, swatches/palette.

### Layout and precision
- [x] **Align and distribute** (to selection or artboard; Align panel). Key object still open.
- [x] **Snapping**: nodes, edges, centres, other objects' bounds (smart-guide lines), grid, guides, artboard; Ctrl ignores.
- [x] **Rulers, guides, grid** (guides/grid in Inkscape's SVG format). Angled guides, multiple grids still open.
- [x] **Units**: px / mm / cm / in / pt, document size in units, DPI, panels in the document unit.
- [ ] **Transform panel**: numeric X/Y/W/H/rotation for multi-selection, chosen reference point. (Single objects already have numeric fields in the selection panel.)

### Document and app
- [x] **New document size**: New Document dialog with presets (A4, Letter, 1080p, …), custom size, unit, DPI, orientation.
- [ ] **Document properties**: change size/unit/DPI of an existing document, background colour.
- [x] **Recent files**: File → Open Recent, list in the startup dialog.
- [ ] **Open by drag and drop** onto the window.
- [x] **Crash recovery**: snapshots while unsaved (interval setting), Recover dialog after a crash, one backup of the previous version on save. (Autosave into the user's own file deliberately not done.)
- [x] **Settings window**: categories + pages (General, Language, Canvas).
- [ ] **More settings**: nudge step, undo depth, theme, default unit.
- [ ] **Keyboard shortcut overview** (and later customization).
- [ ] **Export**: PDF, JPEG/WebP, plain/optimized SVG, export selection only, multiple sizes at once. (SVG via Save As and PNG with DPI exist.)
- [ ] **Import images** → SVG Level 5.
- [ ] **Print**.

## Editor features: P2, core professional depth

### Paint
- [ ] **Gradients** → SVG Level 3; later mesh/freeform gradients.
- [ ] **Patterns** → SVG Level 3.
- [ ] **Blend modes** (CSS `mix-blend-mode`, SVG 2 / Compositing; beyond the 1.1 suite).
- [ ] **Multiple fills and strokes per object** (appearance stack, Illustrator/Affinity style). SVG export needs a fallback (stacked copies).
- [ ] **Global/linked colors**: change one swatch, every user updates.

### Paths
- [ ] **Stroke to path**, **offset path** (inset/outset), **simplify**, reverse direction.
- [ ] **Join / break / cut paths**, close path, combine and split compound paths.
- [ ] **Knife / scissors tool**, eraser.
- [ ] **Shape builder** (drag across regions to merge or remove; Composites and divide are the base).
- [ ] **Node tool extras**: node types (corner/smooth/symmetric) buttons, align nodes, add nodes by count.
- [ ] **Corner rounding** on any path node (live corners).

### Text
- [ ] **Multi-line and area text** (text in a box with wrapping), line height. (Left/centre/right alignment of single lines done.) Area text has no SVG 1.1 form: SVG 2 `shape-inside` or positioned tspans on save.
- [ ] **Font picker**, per-character styling, letter spacing, text on path → SVG Level 7.
- [x] **Text to outlines**: Object to Path (Ctrl+Shift+C). Revisit with rich text.
- [ ] OpenType features (ligatures, alternates).

### Objects and structure
- [ ] **Layers panel upgrade**: drag to reorder, nest layers, layer opacity, object names. (Object tree and layer locks done.)
- [x] **Clipping masks and opacity masks** (done 2026-10-23, spec `svg-conformance-level4`): Object → Clipping Mask / Opacity Mask.
- [ ] **Symbols / components** (edit once, update all instances; `<symbol>` + `<use>` kept as links instead of expanded on import).
- [ ] **Multiple artboards / pages**.

### Effects (non-destructive)
- [ ] Drop shadow, blur, inner/outer glow → SVG Level 8.
- [ ] Live path effects: round corners, offset, roughen, pattern along path.

### Files
- [x] **Native file format** (lossless, versioned).
- [ ] **SVG conformance** → levels above. (Done 2026-10-20: CSS class/id styles, `<use>`/`<symbol>`, tspan lines, text anchor, opacity, fill rule, stroke options, rounded rects, import report dialog.)
- [ ] **PDF import**.
- [ ] AI/EPS import: hard; maybe via PDF compatibility of modern .ai files.

## Editor features: P3, advanced, and where PressToShape could stand out

- [ ] **Tablet pressure**, vector brushes, variable-width strokes with width profiles (product pillar 1, the artist focus). SVG export as filled outlines.
- [ ] **Image trace** (bitmap to vector).
- [ ] **Perspective / envelope / free distort** tools.
- [ ] **Blend tool** (interpolate between shapes).
- [ ] **Command search / palette** (registries already make this cheap), customizable shortcuts and toolbars.
- [ ] **Scripting / plugin API** (operations registry as the base).
- [ ] **Export slices/assets** for UI design (per-object export at 1x/2x/3x).
- [ ] **History panel** (undo steps are already labelled).
- [ ] **Navigator / overview panel**, outline (wireframe) view mode, pixel preview.
- [x] **Localization** (UI translations): English + German, user .po files, Settings window.
- [ ] **Accessibility** pass (keyboard navigation of panels, screen reader names).

## Distribution and project (not editor features)

- [ ] Code signing for Windows (removes the SmartScreen warning).
- [ ] Stable versioned releases next to nightlies; in-app update check (opt-in, since the app is offline by principle).
- [ ] More Linux formats: Flatpak (Flathub), maybe .deb/.rpm.
- [ ] File associations for `.svg` (MSI, desktop entry).
- [ ] CI on every push/PR (tests + lint), not only nightly. The conformance check (Level 0) belongs there too.
- [ ] Final app icon (current one is a placeholder).
