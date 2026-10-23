# Requirements Document

## Introduction

Level 5 of the SVG conformance roadmap: **images**, built as a real editor feature ("Import images" is an editor P1 item in the feature gap list). Today `<image>` is dropped on import (`Note.IMAGE`: "{count} image was left out"), nothing can be placed, and files from Inkscape or Illustrator with traced-over photos or embedded textures lose them. In the W3C suite the `struct-image` group and the image cases of `coords-viewattr` and `struct-symbol` match 4 of 20+ tests.

The level adds an **image object** that serves two jobs:

- **Artwork**: place a PNG/JPEG/WebP/GIF in the document, move, scale, rotate, flip, set opacity, mask it, export it.
- **Reference**: trace over a photo or sketch. A reference image is locked, drawn dimmed, and neither exported nor printed.

Includes:

- **Model**: a frozen `ImageShape` (position, size, `preserveAspectRatio`, opacity, `reference` flag) pointing at an `ImageData` blob (encoded bytes + pixel size + content hash). The bytes are embedded; the shape stays small and cheap to copy for undo.
- **Place**: File → Place Image… (multi-select), drag and drop onto the window, paste of a bitmap from the clipboard. Place at the centre of the visible area, at its pixel size (1 px = 1 document pixel), shrunk to fit the page when larger.
- **Reader**: `<image>` with `href`/`xlink:href` as `data:` URI or relative file path, `x y width height`, `preserveAspectRatio` (all align values, meet/slice, `none`), `transform`, `opacity`, `display`/`visibility`, `clip-path`/`mask` (through Level 4), `<image>` inside `<symbol>`/`<use>`/nested `<svg>`.
- **Render**: Skia `drawImageRect` with sampling that follows zoom (nearest when enlarging past a threshold, linear/mipmap when shrinking), decoded once and cached by content hash.
- **Save**: SVG writes `<image>` with a base64 `data:` URI; `.p2s` stores the bytes once per distinct image as a media entry in the ZIP.
- **Editor**: Object → Image menu (Embed is implied; Replace…, Reset Size, Fit to Page, Make/Release Reference), image selection panel, Layers panel row with a thumbnail.

Decisions taken before writing (2026-10-23), open to change in the approval:

- **One model, two roles.** An image is an `ImageShape`; "reference" is a flag on it, not a second type. Same hit-test, bounds, transform and Layers behaviour; only the flag changes rendering (dimmed), locking and export.
- **Always embedded in the document.** The editor never keeps a link to the file after placing; a document stays self-contained and portable. Linked `href`s in opened SVG files are read and embedded at import. Linking as a user option (smaller files, edits in an external editor) is out of scope; the model leaves room for it (`ImageData` could later carry a path).
- **Decode with Skia, not Qt.** `skia.Image.MakeFromEncoded` handles PNG, JPEG, WebP and GIF (first frame) below `views/`, so import and render stay Qt-free and testable. Formats Skia cannot decode are refused with a message.
- **Original bytes are kept**, not re-encoded: no quality loss on save, no generation loss in JPEG, small `.p2s` and SVG. EXIF orientation is applied at decode (Skia's codec origin), not by rewriting bytes.
- **References are not exported.** PNG export skips them; SVG save does not write them and says so in the save status ("{count} reference image was not saved to SVG"). `.p2s` keeps them. Rationale: they are scaffolding, and a photo-sized blob in every exported logo is the common accident.
- **No SVG-in-image.** `<image href="x.svg">` is read as an unsupported type and noted (nested documents, recursion, security); raster only.
- **No raster editing.** No crop tool, filters, colour adjustments or trace here. Crop is done with a clipping mask (Level 4). Image trace is a P3 item of its own.
- **Resolution is the user's business.** No resampling of the source on scale; the app shows the effective PPI of a placed image in its panel.

Out of scope: linked images as a document mode, image embedding choices (JPEG recompression), 16-bit/CMYK/ICC handling beyond what Skia does, animated GIF/APNG playback, pattern fills with images (pattern spec), `<feImage>` (filters level), `<foreignObject>` (non-goal), `<image>` with `href` to an element id (SVG 2 `<use>`-like).

## Alignment with Product Vision

- **Principle 4, own format for fidelity, SVG for exchange**: images stop being silently dropped; `.p2s` stores them losslessly, SVG gets the standard `<image>` form.
- **Principle 5, Inkscape interop**: Inkscape's embedded and linked images open, and our saved `<image data:…>` opens in Inkscape as an embedded image.
- **Principle 6, WYSIWYG**: canvas, PNG export and the saved SVG (checked against resvg) match, including `preserveAspectRatio` and opacity.
- **Success metric, Interop**: photos, textures and scans are common in real-world files; today they vanish.
- **Target users**: illustrators trace over sketches and photos (reference images), designers place logos and mock-up photos (artwork images). Reference images are the first piece of the illustrator workflow outside pure vector tools.
- **Principle 3, non-destructive**: images are never modified; masks crop them.

## Requirements

### Requirement 1: Image object in the model

**User Story:** As a user, I want an image to be an object like any other, so I can move, scale, rotate, hide, lock, group and mask it.

#### Acceptance Criteria

1. `models/shapes.py` SHALL define a frozen `ImageData` (`data: bytes`, `width: int`, `height: int` pixel size, `digest: str` content hash used as identity) and a frozen `ImageShape` with `id`, `x`, `y`, `width`, `height` (the image viewport in user space, as SVG `<image>`), `data: ImageData`, `aspect: PreserveAspectRatio` (align, meet/slice; default `xMidYMid meet`), `opacity`, `transform`, `reference` (bool), `hidden`, `locked`. It has no `Style`.
2. `Shape` SHALL include `ImageShape`; code that reads `shape.style` SHALL handle `ImageShape` next to groups (drawing, hit-testing, bounds, `restyle_shape`, transforms, encoders, clipboard, SVG writer, booleans, align, snapping targets). A table test SHALL list every `match shape` over shape types so a new type cannot be missed (same guard as for `MaskGroup`).
3. `ImageData` SHALL compare by `digest`, not by bytes, so equal images are cheap to compare and undo snapshots share one blob. Two shapes with equal data share one `ImageData` object after paste, duplicate and file load.
4. `models.shapes.sanitized` SHALL keep width/height finite and non-negative, `opacity` in 0..1 and `aspect` in its enum; a zero-size image draws nothing and does not raise.
5. Transforms SHALL go through `geometry.transforms` (`transform_shape`, `translate`, `with_rotation`); the shape keeps a canonical transform like rects do; an image can be rotated and flipped, and skew is kept as read.
6. Tests: construction, sanitising, digest equality, shared blob after copy, canonical transform, `children_of` unaffected.

### Requirement 2: Decoding and the image cache

**User Story:** As a user, I want any normal image file to place without surprises, and a broken one to be refused with a clear message.

#### Acceptance Criteria

1. A new Qt-free module (`render/images.py`) SHALL load encoded bytes into `ImageData` (sniffing the content type by signature, not by extension): PNG, JPEG, WebP, GIF (first frame). Anything else, a zero-byte file or an undecodable file SHALL raise a typed error carrying a translatable message; nothing else is raised to callers.
2. Limits SHALL be enforced before decoding: encoded size at most 64 MiB, pixels at most 100 megapixels; both refuse with a message naming the limit (hostile or accidental huge files must not hang or exhaust memory).
3. EXIF orientation SHALL be applied: the stored pixel size is the displayed size, and rendering rotates accordingly.
4. A decode cache keyed by `digest` SHALL hold decoded `skia.Image`s with a memory budget (setting-free constant, least-recently-used eviction); a document with 50 distinct large photos SHALL not hold all of them decoded at once. Texture upload for the GPU path happens lazily on first draw.
5. The cache SHALL be an object owned by the render layer and passed in (no module-level state, per the architecture rules); the `Session` or scene creates one per window.
6. Tests: each format decodes with correct size; EXIF rotation; corrupt/empty/truncated/unsupported (SVG, TIFF, PDF) refused; limits; cache eviction order; decoding does not import Qt.

### Requirement 3: Placing images in the editor

**User Story:** As an artist, I want to put a picture on the canvas in seconds, as artwork or as a reference to trace.

#### Acceptance Criteria

1. Registered operations SHALL exist: `Place Image…` (window command, file dialog with image filter, multi-select) and the plain operation `place_images(session, items, position)` taking already-loaded `ImageData`. Dialogs stay in views, the operation takes plain values.
2. File → Place Image… SHALL place each chosen file at the centre of the visible canvas, offset a little per file so stacked images are visible; selected after placement; one undo step labelled "Place Image" / "Place {count} Images" (translated, `ngettext`).
3. Size at placement SHALL be the pixel size in document pixels (1 image pixel = 1 document pixel), shrunk proportionally to fit within 80 % of the page when larger. Images placed from a file that has DPI metadata SHALL NOT change size by it (documented; the panel shows effective PPI).
4. Dragging image files onto the window SHALL place them at the drop point; non-image drops are ignored with a status message. (Drag-and-drop of `.svg`/`.p2s` to open is a separate gap item; this requirement only routes image types and does not change that.)
5. Pasting a bitmap from the system clipboard (screenshot, "copy image" from a browser) SHALL place it at the centre like Place does; when the clipboard holds both shapes and a bitmap, shapes win (existing behaviour unchanged).
6. The image goes into the active container (layer, entered group), through `editing/containers.py`. Placement into a locked or hidden layer follows the existing rules for new shapes.
7. `Place as Reference…` (a second menu entry, same dialog) SHALL place with `reference=True` into a layer named "Reference" created on first use (locked, below others; a layer the user already named "Reference" is reused). This is a normal layer, undoable with the placement.
8. Refusals (unreadable file, too large, unsupported type) SHALL show one message that names the file and the reason; other files in the same batch are still placed.
9. No default shortcut for Place Image (rare command, ask before adding one, per the keymap rule); Place is reachable from the File menu and the empty-document start dialog hint.
10. Tests: place one/several, size rules (small, large, exact page), container, undo/redo labels, selection afterwards, each refusal, reference layer creation and reuse.

### Requirement 4: Selecting and editing images

**User Story:** As a user, I want to work with a placed image like with shapes, and fix its size or swap its file later.

#### Acceptance Criteria

1. Select tool: click picks an image where its drawn area is (inside the `preserveAspectRatio` fitted rectangle, not the whole viewport); rubber-band, shift-click, move, scale handles (proportional by default for images, Shift toggles to free; design confirms the exact rule), rotate, flip, nudge, align/distribute, snapping targets (bounds corners and centres), group/ungroup, raise/lower, duplicate, copy/cut/paste, delete work as for other objects.
2. Locked and hidden objects follow existing rules; reference images SHALL be locked on creation and hit-test as locked (not selectable on the canvas; selectable in the Layers panel to change them).
3. Style panel with an image selected SHALL show only what applies: opacity (object); fill, stroke and fill rule fields disabled with the same pattern as for `GroupShape`. The selection panel SHALL show X/Y/W/H/rotation as for other shapes plus the pixel size and effective PPI (`pixels / (size in inches)`), read-only.
4. Operations SHALL exist as registered commands under Object → Image: `Reset Image Size` (back to pixel size, keeping the centre), `Fit Image to Page` (proportional, centred), `Replace Image…` (window command: file dialog, keeps position, size box and transform; the new image gets `meet`-fitted into the same box), `Make Reference` / `Make Artwork` (toggle `reference`; making a reference locks and dims it), `Show/Hide References` as a view toggle (view state on `AppState`, saved in `.p2s` working state like grid visibility).
5. A reference image SHALL draw at 40 % opacity combined with its own opacity (the dimming amount is a constant; no setting yet), never above the artwork of the layer order, and SHALL NOT be included in selection-all.
6. Booleans, Composite creation, Make Clipping Mask as the mask object, node editing, stroke-to-path and anything else that needs geometry SHALL refuse a selection containing an image with a status message that names the reason ("Images cannot be combined"); an image can be the content of a clipping/opacity mask (and a mask object in an opacity mask, where it contributes its luminance) and a child of a group.
7. Object → Image entries SHALL be disabled (`can_run`) when no image is selected. Mnemonics must not clash (test).
8. Layers panel: an image row SHALL show a thumbnail (rendered from the decode cache at row height, generated lazily and not on every refresh), the eye/lock toggles, and a reference marker. Renaming is not needed (rows are unnamed like other objects).
9. Tests: every operation (positive and refused cases), undo labels, selection after, `can_run`, panel field state for image selections, reference lock behaviour, show/hide references.

### Requirement 5: Rendering

**User Story:** As a user, I want images sharp at 100 %, smooth when zoomed out, and fast with many of them.

#### Acceptance Criteria

1. `render/` SHALL draw an `ImageShape` with `drawImageRect` into the `preserveAspectRatio`-fitted rectangle, clipped to the viewport rectangle for `slice`, with the shape's `transform`, `opacity` and the reference dimming; anti-aliased edges after rotation.
2. Sampling SHALL depend on the on-screen scale: nearest neighbour when enlarged by 2× or more (pixel art stays crisp), linear with mipmaps otherwise. Export uses the same rules at its scale.
3. Decoding SHALL happen once per `digest` through the cache of Requirement 2.4; panning and zooming SHALL decode nothing and upload nothing new. Very large images SHALL draw from a prescaled mip/level when zoomed far out so a 100-megapixel photo does not cost a full-resolution draw per frame.
4. An image with opacity below 1 SHALL be drawn with a paint alpha, not a layer. A group with opacity containing images keeps the existing layer rule.
5. The recorded picture (`render/picture.py`) SHALL reuse images by reference to the cached `skia.Image`; moving or rotating images during a gesture SHALL go through `Overlay.matrix` and keep the picture.
6. A missing or undecodable image (cache miss on a corrupt blob) SHALL draw a visible placeholder (outline plus cross) instead of nothing or an exception, on canvas and in export.
7. Images inside `MaskGroup` (clip content, luminance mask objects) SHALL render, so the open items from Level 4 (`masking-path-04-b`, `-06-b`, `-07-b`, `-11-b`) are decided here.
8. PNG export SHALL render images through the same scene code; reference images are skipped.
9. Hit-testing and bounds use the fitted rectangle with the shape's transform (so clicking the empty letterbox of a `meet` image does not pick it); pixel transparency is not tested.
10. Tests: CPU-surface pixel assertions for each `preserveAspectRatio` align and meet/slice, rotation, opacity, reference dimming, nearest vs linear sampling at 4× zoom, placeholder for a corrupt blob, image in clip and luminance mask; `scripts/bench_canvas.py` extended with 200 mid-size images and the cost recorded in the task log.

### Requirement 6: Reading `<image>` from SVG

**User Story:** As a user opening an SVG with pictures, I want the pictures to show up where they belong.

#### Acceptance Criteria

1. `<image>` with `href` or `xlink:href` SHALL become an `ImageShape` with `x y width height` (percentages and units like other lengths), `preserveAspectRatio` (all aligns, `meet`/`slice`/`defer` ignored/`none`), `transform`, `opacity`, `display`, `visibility`, `clip-path`, `mask` (Level 4 wraps it), and inherited cascade as for shapes.
2. `data:` URIs SHALL be decoded (base64 and percent-encoded forms; `image/png`, `image/jpeg`, `image/webp`, `image/gif`, and `application/octet-stream` or missing type by signature). A `data:image/svg+xml` image SHALL be left out with the note of Requirement 6.6.
3. Relative file paths SHALL be resolved against the opened file's folder (`formats` receives the base folder as an argument; no global). Absolute paths and `file://` URLs inside the same user-owned tree are allowed; **`http(s)://` and any other scheme SHALL NOT be fetched** (note: "{count} linked image was not loaded: remote address"). Paths that climb above the filesystem root or resolve through a symlink to a non-regular file SHALL be refused; special files (devices, FIFOs) never opened.
4. `width`/`height` of 0 or negative: nothing drawn (SVG rule; SVG 1.1 disables rendering). Missing `width`/`height` (SVG 2 auto): use the image's pixel size. Both are covered by tests.
5. The linked file SHALL be read once per distinct path per import and embedded; the same data referenced by several `<image>` elements SHALL share one `ImageData`.
6. Notes (counted, translated, replacing `Note.IMAGE`): "{count} image was left out: file not found", "…: not a supported image type", "…: remote address", "…: too large", "{count} SVG image was left out". Each reason separately counted so the user can act.
7. `<image>` inside `<symbol>`, `<use>`, nested `<svg>`, `<switch>` and `<a>` SHALL work like other content (`struct-symbol-01-b`, `struct-image-*`, and the `<image>` cases of `coords-viewattr-02-b` / `-04-f` left open by Level 2).
8. The Level 1 root `preserveAspectRatio` code and the new image code SHALL share the align/meet/slice math (`geometry/`), not duplicate it.
9. Hostile input (a `data:` URI of 500 MB, 10 000 `<image>` elements with the same URI, a path to `/dev/zero`, a file that is a decompression bomb) SHALL be handled by the limits of Requirement 2 and by an overall cap on embedded bytes per import (256 MiB) with a note when exceeded; never a hang, a crash or a non-finite value.
10. Tests: every rule above, plus the `struct-image-*` and `coords-viewattr` cases of the suite.

### Requirement 7: Saving and round trips

**User Story:** As a user, I want pictures to survive save and reopen in PressToShape and in other programs.

#### Acceptance Criteria

1. Saved SVG SHALL write `<image>` with `x y width height`, `preserveAspectRatio` (omitted when default), `opacity` (omitted at 1), `transform` and an embedded `href="data:image/…;base64,…"` of the original bytes (`xlink:href` as well if the design finds viewers that need it, checked in resvg). Hidden images follow the existing `display` handling.
2. Each `<image>` SHALL carry its own data URI; deduplicating shared images through `<defs>` and `<use>` is optional and left to the design (file size versus compatibility; Inkscape reads both).
3. Reference images SHALL NOT be written to SVG (Introduction), the save status says how many were left out; "Save As SVG" with only reference images produces an empty drawing as for any empty document.
4. The saved file SHALL render identically in resvg and on our canvas for each case of Requirement 5.10 (existing check in `tests/formats/test_svg_generator.py`).
5. `.p2s` SHALL store each distinct `ImageData` once as a binary media entry in the ZIP (`media/<digest>.<ext>`), referenced from the shape by digest; unreferenced media are dropped on save; explicit encoder/decoder (no dataclass walk). `CURRENT_VERSION` SHALL be bumped (10) with a migration from version 9, a `tests/formats/samples/v10.p2s` sample that contains an image, and a row in `docs/file-format.md` (including the media rules and the limits).
6. Loading a `.p2s` with a missing or corrupt media entry SHALL open the document with that image as the placeholder of Requirement 5.6 and a load note, never fail the whole file.
7. The clipboard payload SHALL carry `ImageShape` with its bytes (size cap as for placement); pasting into another PressToShape window keeps the image; the SVG on the clipboard for other apps carries `<image>` as saved SVG does. Pasting back an image-only SVG payload from our own app SHALL reproduce an equal model (same digest).
8. Crash recovery snapshots SHALL include images (they are `.p2s`), and the snapshot interval rule stays; a 200 MB document SHALL not make the keeper block the UI thread longer than a frame (write off the UI thread or document the measured cost; design decides).
9. A document opened from SVG, saved as `.p2s`, reopened and saved as SVG SHALL produce an equal image (bytes, box, aspect, opacity).
10. Tests: SVG round trip for each aspect value, opacity, rotation, in a group and in a mask; `.p2s` round trip including the shared blob and unreferenced-media drop; migration from the v9 sample; corrupt media; clipboard round trip; reference images not in SVG.

### Requirement 8: Updated baseline and documents

**User Story:** As the maintainer, I want the conformance numbers and the docs to reflect this level.

#### Acceptance Criteria

1. Every `struct-image-*`, `struct-symbol-01-b`, `coords-viewattr-02-b`, `coords-viewattr-04-f` and `masking-path-04-b/-06-b/-07-b/-11-b` test that now matches SHALL be added to `tests/scripts/svg_conformance_pass.txt` after a check by eye; mismatches stay as `!name # reason` (external-document and remote-URL cases keep an explicit reason).
2. `docs/svg-conformance.md` SHALL be regenerated; `.spec-workflow/steering/product.md` / `tech.md` import-gap lines updated (images removed from "skipped or approximated"; image support added to the feature list).
3. The feature gap list SHALL tick: Level 5 `<image>` embedded/linked and place-in-editor, editor P1 "Import images", the Level 4 items waiting for images, and note the external `<use>` item as still open (separate spec or Level 5b). Because the gap list is local-only, this is a note to the maintainer in the final task, not a repository change.
4. `README`/FAQ wording on images SHALL be hedged per the existing rule (no claims beyond what is tested).
5. `main.py --self-test` SHALL decode a tiny embedded PNG, JPEG and WebP so a frozen bundle missing a Skia codec fails the build.
6. No test on the pass list before this level SHALL leave it. Target: at least 15 of the `struct-image-*` plus related cases match; the rest have a documented reason.

## Non-Functional Requirements

### Code Architecture and Modularity
- Decode, cache and limits in `render/images.py`; the pure box/aspect math in `geometry/` (shared with Level 2's root viewport code); reader in `formats/svg_images.py` (data-URI and path resolution, limits, notes) called by `svg_reader.py`; writer part next to the existing shape writers; operations in `editing/operations/images.py`; media encoding in `formats/p2s.py` with the migration in `p2s_migrations.py`.
- No Qt below `views/`. The file dialogs, drag-and-drop, bitmap-from-clipboard conversion (to encoded PNG bytes) and the Layers thumbnail live in views and hand plain bytes/`ImageData` to operations. Import direction rules stay (`tests/test_architecture.py`).
- Shapes frozen; `dataclasses.replace`; one `Session` passed explicitly, the decode cache owned by the render/scene object, not a module global.
- Dependencies: Skia already decodes; **no new package** (Pillow stays dev-only and is not used by the app).

### Performance
- Documents without images draw and open as fast as today.
- 200 mid-size images (about 1 MP each) pan and zoom without visible lag on the GL path; memory stays within the cache budget plus encoded bytes. Open time of a 100 MB `.p2s` is dominated by reading the ZIP, not by decoding: decoding is lazy, on first draw.
- Undo snapshots share `ImageData`; placing or moving an image never copies its bytes.

### Security
- No network access, ever: remote `href`s are not fetched. Local paths in files are resolved only as in Requirement 6.3; the app never executes or opens anything but regular image files.
- Size, pixel and total-bytes limits before decoding (Requirement 2.2, 6.9) against decompression bombs; decoder errors never propagate as anything but the typed error.
- Image bytes from a file are untrusted: sniff by signature; the media name in `.p2s` is derived from the digest, never from file contents (no path traversal from a ZIP entry name).

### Reliability
- Every SVG and `.p2s` that opens today still opens. A bad image never prevents the rest of the file from opening and never crashes the canvas; it degrades to the placeholder plus a note.
- Everything the app can save reopens (tested round trips); older `.p2s` files migrate.
- Crash recovery covers placed images; a failed write leaves the previous file intact (existing atomic save).

### Usability
- Place, Place as Reference and the Object → Image entries are discoverable in the menus with clear, translated labels; refusals say why in the status bar. Notes are short and counted.
- A reference image behaves predictably: dim, below the artwork, never in the way of clicks on the canvas, never in an export.
- Translations (`de.po`) complete, `uv run python scripts/update_translations.py` run; mnemonics do not clash.
