# Tasks Document

Every task that adds an import note or UI text runs `uv run python scripts/update_translations.py` and translates the new entries in `de.po` (tests fail otherwise). Every task ends with `uv run ruff check .`, `uv run ruff format .` and the full `uv run pytest` green with the W3C suite fetched, so no pass-list entry regresses. Until task 8 the reader still drops `<image>`, and until task 9 no operation creates images: tasks 1–7 build their images in tests and must not change what any existing file looks like or how it is saved.

- [x] 1. Shared aspect math in geometry
  - Files: presstoshape/geometry/aspect.py (new), presstoshape/formats/svg_viewport.py, tests/geometry/test_aspect.py (new)
  - Move `Aspect`, `parse_aspect`, `fit` (and `_ALIGN_FRACTION`) out of `formats/svg_viewport.py` into `geometry/aspect.py`; `svg_viewport` imports them back so Level 1/2 code and tests are untouched
  - Add `fitted_rect(source_width, source_height, x, y, width, height, aspect)` returning the destination rect and whether it must be clipped to the viewport (slice), and `visible_box` helper input for ImageShape
  - Purpose: one implementation of align/meet/slice for the root viewport, `<image>` and drawing (Req 6.8)
  - _Leverage: `geometry.affine`, `formats/svg_viewport.py`, existing viewport tests_
  - _Requirements: 6.8, 5.1, 5.9_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md `geometry/aspect.py` with tests: moved Level 2 cases still pass through the re-import, `fitted_rect` for every align (9 values and none) × meet/slice × wide/tall/square source and viewport, zero and non-finite sizes | Restrictions: no behaviour change for the existing viewport code, no Qt/skia, the value type `Aspect` stays frozen | Success: full pytest green, W3C pass list unchanged. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Image model
  - Files: presstoshape/models/shapes.py, tests/models/test_image_shape.py (new), tests/models/test_shape_types.py (new or existing table test)
  - Frozen `ImageData(data, width, height, mime, digest)` (equality and hash by digest), `ImageAspect`/`Aspect` value type in models, frozen `ImageShape` per design, add to `Shape`, `children_of` returns empty, `sanitized` rules (finite non-negative size, opacity 0..1, aspect enum, digest shape)
  - Table test that lists every `match shape` / `isinstance` site over shape types (grep-based) so a new type cannot be missed; fix the sites it lists that would raise (`style` access) with the minimal `ImageShape` arm, real behaviour comes in later tasks
  - Purpose: the value type every later task builds on (Req 1)
  - _Leverage: `RectShape`, `GroupShape`, `sanitized`, `children_of`_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md `models/shapes.py` section with unit tests: construction, sanitising, digest equality, shared blob after `replace`, empty size draws nothing and never raises | Restrictions: frozen dataclasses, no Qt/skia, `geometry` cannot be imported from models (so `Aspect` lives here), no behaviour change for existing shapes | Success: tests green, nothing else changes behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Image header probe
  - Files: presstoshape/formats/image_info.py (new), tests/formats/test_image_info.py (new)
  - `probe(data) -> ImageData`: signature sniff for PNG/JPEG/GIF/WebP, dimensions from IHDR/SOF/GIF screen/VP8/VP8L/VP8X, JPEG EXIF orientation 5–8 swaps size, sha-256 digest
  - Limits before any decode: 64 MiB bytes, 100 MP pixels; typed `ImageError(reason)` with `empty | unsupported | corrupt | too_large | too_many_pixels` and a `message(name)` helper with translated texts
  - Tiny fixtures generated in tests (no big binaries committed)
  - Purpose: type, size and limits for the reader, placement and `.p2s` without Skia (Req 2.1, 2.2)
  - _Leverage: `hashlib`, `presstoshape.i18n`_
  - _Requirements: 2.1, 2.2, 2.3_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md `formats/image_info.py` with tests: each type, EXIF rotation, truncated headers at every byte offset of a small file, zero and huge dimensions, garbage, SVG/TIFF/PDF refused as unsupported, limits, the module imports neither Skia nor Qt | Restrictions: pure Python, no new dependency, never read past the buffer, never raise anything but `ImageError` | Success: tests green incl. a loop fuzz of truncations and random bytes. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Decode cache and image drawing
  - Files: presstoshape/render/images.py (new), tests/render/test_images.py (new)
  - `ImageCache(budget_bytes)` with LRU by decoded size, remembered decode failures, mip level for images over 16 MP at scale < 0.5, `get(data)`, `trial_decode(data)`
  - `draw_image(canvas, shape, image_or_none, opacity)`: destination from `geometry.aspect.fitted_rect`, `clipRect` for slice, nearest sampling at device scale ≥ 2 (read from `canvas.getTotalMatrix()`), linear + mipmap otherwise, paint alpha for opacity; `draw_placeholder` hairline box with cross
  - EXIF origin applied on decode
  - Purpose: pixels on screen and in export, decoded once per digest (Req 5.1–5.3, 5.6)
  - _Leverage: `geometry.aspect`, skia `Image.MakeFromEncoded`, `PathCache` validity ideas_
  - _Requirements: 2.3, 2.4, 2.5, 2.6, 5.1, 5.2, 5.3, 5.4, 5.6, 5.10_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with Skia experience | Task: Implement design.md `render/images.py` with CPU-surface pixel tests: each align and meet/slice, rotation via canvas matrix, opacity, nearest vs linear at 4× zoom, placeholder for a corrupt blob, EXIF rotated JPEG, eviction order and budget, huge-image mip level chosen, failed decode tried once | Restrictions: no module-level state, no Qt, no decode per frame, no layer for opacity | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Scene, path cache, hit-test, handles, transforms, export
  - Files: presstoshape/render/paths.py, presstoshape/render/scene.py, presstoshape/render/hit_test.py, presstoshape/render/handles.py, presstoshape/render/export.py, presstoshape/geometry/transforms.py, tests/render/test_image_scene.py (new), tests/geometry/test_image_transforms.py (new)
  - `PathCache.images` (an `ImageCache`), `_build(ImageShape)` = visible-box rect path with transform; `draw_shape` ImageShape arm before `shape.style` (groups-first rule) with transform, opacity and `REFERENCE_OPACITY = 0.4`; `draw_document(..., references=True)`; `render_png` passes `references=False`
  - `hit_test` uses the drawn area and skips `reference` images; `handles.local_bounds` and `selection_frame` use the viewport box; `ImageShape` joins the `RectShape` arms in `translate`, `transform_shape`, `with_rotation`, flips, `_center`
  - Images inside clip/mask `GroupShape` draw (Level 4 path), recorded picture reuses the cached image
  - Purpose: images are drawn, picked, scaled, rotated and exported like other objects (Req 4.1, 5)
  - _Leverage: `PathCache._build`, `RectShape` arms, `draw_document`, `Overlay.matrix`_
  - _Requirements: 4.1, 4.2, 5.1, 5.5, 5.7, 5.8, 5.9, 5.10_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md components `render/scene.py … export.py` and `geometry/transforms.py` with tests: draw/hit/bounds with meet letterbox, reference skipped in export and not hit, translate/scale/rotate/flip keep box and aspect, image in clip and luminance mask (pixels), group with opacity, gesture overlay keeps the picture, snapping targets use the drawn area | Restrictions: no behaviour change for documents without images, no signature change of `draw_shape`, hit-testing never decodes pixels | Success: tests green; before and after `scripts/bench_canvas.py` (no images) recorded in the task log, unchanged. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. `.p2s` version 10 and clipboard
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, presstoshape/formats/clipboard.py, tests/formats/test_p2s.py, tests/formats/test_clipboard.py, tests/formats/samples/v10.p2s (new), docs/file-format.md
  - Image shape object with `media` digest; ZIP entries `media/<digest>.<ext>` (stored), written once per distinct blob reachable via `children_of`, unreferenced never written; read limits (entry ≤ 64 MiB, ≤ 10 000 entries, total ≤ 1 GiB), digest recomputed and compared, entry names never used as paths
  - Missing or corrupt media → placeholder `ImageData` (`mime="application/x-missing"`) plus a load note returned with the document; `CURRENT_VERSION = 10`, `MIGRATIONS[9]` no-op, sample with an image, docs row and Media paragraph
  - Clipboard payload `media` table (cap 128 MiB, else image dropped with a message), blobs interned by digest on decode
  - Purpose: images survive save, open, crash recovery and copy/paste (Req 7.5–7.8)
  - _Leverage: `_encode_shape`/`_decode_shape`, `_read_entry`, `write_p2s`, migration tests, `formats/clipboard.py`_
  - _Requirements: 7.5, 7.6, 7.7, 7.8, 7.9, 7.10_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md `formats/p2s.py` and `clipboard.py` sections with tests: round trip incl. shared blob and unreferenced-media drop, nested in groups and masks, missing/corrupt/digest-mismatching media, hostile ZIP names and counts, v9 sample still opens, v10 sample opens, clipboard round trip and size cap, recovery snapshot contains images | Restrictions: explicit encoders/decoders, never generic over dataclass fields; files without images stay byte-identical apart from the version number; `ImageData` interned per read/paste call, no global | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. SVG writer for images
  - Files: presstoshape/formats/svg.py, presstoshape/formats/svg_notes.py, tests/formats/test_svg_images_writer.py (new), tests/formats/test_svg_generator.py
  - `ImageShape` → `<image>` with `xlink:href` data URI of the original bytes, `preserveAspectRatio` and `opacity` omitted at defaults, `transform`, `display="none"` for hidden; reference images skipped and counted in the save result so the status reads "{count} reference image was not saved to SVG"
  - Resvg generator check for each aspect value, opacity, rotation, image in a group and in a clip/luminance mask
  - Purpose: saved SVG contains the pictures and renders like the canvas (Req 7.1–7.4)
  - _Leverage: `_untransformed_element`, `write_shapes_svg`, generator-check helpers_
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.9, 7.10_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md writer section with tests incl. the resvg comparison; confirm `xlink:href` alone renders in resvg and note the result in the task log (if not, write both) | Restrictions: files without images byte-identical to today's output; reference images never written | Success: tests green incl. resvg comparison. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. SVG reader for `<image>`
  - Files: presstoshape/formats/svg_images.py (new), presstoshape/formats/svg_reader.py, presstoshape/formats/svg_notes.py, presstoshape/editing/operations/documents.py, tests/formats/test_svg_images.py (new)
  - `read_image` per design: `data:` (base64/percent), relative path against the opened file's folder, `file:` URL; other schemes refused (`IMAGE_REMOTE`), `image/svg+xml` refused (`IMAGE_SVG`); regular files only, size checked before reading; 256 MiB per-import budget, interning by path and digest; missing/auto/zero/negative `width`/`height` rules; `preserveAspectRatio` via `geometry.aspect`
  - Replace `Note.IMAGE` with `IMAGE_MISSING`, `IMAGE_UNSUPPORTED`, `IMAGE_REMOTE`, `IMAGE_TOO_LARGE`, `IMAGE_SVG` (counted, `ngettext`); `base_folder` argument through `read_svg`/`read_document`, `documents.py` passes the folder, clipboard SVG passes `None`
  - `<image>` inside `<symbol>`, `<use>`, nested `<svg>`, `<switch>`, `<a>`; Level 4 clip/mask wrapper applies automatically
  - Purpose: pictures in opened SVG files show up where they belong (Req 6)
  - _Leverage: `_visit_shown`, `svg_masks` wrapper, `svg_lengths`, `Note` table, `import_report_dialog`_
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md `formats/svg_images.py` with tests per Req 6.10: data URI forms, relative/absolute/`file:`, remote refused with no network access (assert no socket use), symlink to special file and device path refused, 10 000 elements with one URI read once, 500 MB URI refused before decoding, budget exceeded note, auto/0/negative size, every aspect value, symbol/use/switch/nested svg, each note counted; run `uv run python scripts/update_translations.py` and translate new entries in `de.po` | Restrictions: never fetch anything over the network, never open non-regular files, no exception out of the reader | Success: tests green, translation tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Image operations
  - Files: presstoshape/editing/operations/images.py (new), presstoshape/editing/queries.py, presstoshape/editing/object_tree.py, presstoshape/editing/operations/style.py, presstoshape/editing/operations/booleans.py, presstoshape/editing/operations/composites.py, presstoshape/models/app_state.py, presstoshape/formats/p2s.py (state field only), tests/editing/test_images.py (new)
  - `place_images(session, items, center, reference=False)` with the size rule (pixel size, shrink to 80 % of the page), per-item offset, active container via `add_on_top`, selection, one `ngettext` undo step; reference placement finds or creates the locked bottom "Reference" layer inside the same edit; `PlaceResult` with refusals (trial decode)
  - Registered `image.reset_size`, `image.fit_page`, `image.make_reference`, `image.make_artwork` with `can_run`; `replace_image` (keeps box and transform, refits height to the new aspect); `set_show_references` with `AppState.show_references` stored as optional working state
  - Refusals with status messages in booleans, composites, node editing and clip-mask-as-clip-object for selections containing images; `object_type`/`object_label` for image and reference; style operations touch only `opacity` of images
  - Purpose: all editor behaviour of images below the views (Req 3, 4.4–4.7)
  - _Leverage: `_document.add_on_top`, `insert_copies`, `containers`, `@operation`, `ngettext`, `Session.edit`_
  - _Requirements: 3.1, 3.2, 3.3, 3.6, 3.7, 3.8, 3.10, 4.2, 4.4, 4.5, 4.6, 4.7, 4.9_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md `editing/operations/images.py` and the listed touches with tests per Req 3.10 and 4.9: sizes (small, large, exactly page), container (layer and entered group), undo/redo labels and selection, reference layer create + reuse, every command with and without image selected (`can_run`), each refusal message, show/hide references, `replace_image` refit; run `uv run python scripts/update_translations.py` and translate in `de.po` | Restrictions: operations take plain values (`ImageData`, points), no dialogs, no Qt; reference placement is one undo step; rejected input still `notify()`s | Success: tests green, translation tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 10. Menus, dialogs, drop and bitmap paste
  - Files: presstoshape/views/keymap.py, presstoshape/views/main_window.py, presstoshape/views/canvas_view.py, presstoshape/views/clipboard.py, presstoshape/icons.py, scripts/generate_icons.py, presstoshape/assets/icons/*.svg, tests/views or tests/test_keymap.py
  - File → Place Image…, Place as Reference…; Object → Image submenu (Reset Size, Fit to Page, Replace…, Make Reference, Make Artwork); View → Show References (checkable `checked` callback); no shortcuts; Tabler icons `photo`, `photo-plus`, `replace`, `photo-off` generated
  - `MainWindow.place_image/place_reference/replace_image`: `QFileDialog.getOpenFileNames` with `N_` filter, bytes read in the view (I/O boundary), refusals shown in one message listing file and reason
  - Drag and drop of image files onto the window (drop point via `Viewport.to_doc`; non-image drops ignored with status message); `QMimeData.hasImage()` → PNG bytes → `place_images` when no shapes/SVG on the clipboard
  - Purpose: users can bring pictures in by menu, drop and paste (Req 3.2, 3.4, 3.5, 3.9)
  - _Leverage: `WINDOW_COMMANDS`, existing Open/Export dialogs, `views/clipboard.py`, `SvgIconEngine`_
  - _Requirements: 3.2, 3.4, 3.5, 3.7, 3.9, 4.4, 4.7_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python/PySide6 developer | Task: Implement design.md `views/` section (menus, dialogs, drop, bitmap paste) keeping `CanvasView` free of tool/type checks; keymap tests (ids exist, no clashing mnemonics, no new shortcuts); regenerate icons with `uv run --group dev python scripts/generate_icons.py`; run `uv run python scripts/update_translations.py` and translate in `de.po` | Restrictions: connect `triggered` through `lambda`, no defensive try/except around Qt, only I/O boundaries guarded, views never assign to `AppState` | Success: ruff + pytest green; headless QTest script (scratch) places an image through the slot and by simulated drop, offscreen. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 11. Selection panel, Layers thumbnail, references on canvas
  - Files: presstoshape/views/selection_view.py, presstoshape/views/style_editor.py, presstoshape/views/object_tree_model.py, presstoshape/views/layers_view.py, presstoshape/views/main_window.py, presstoshape/views/canvas_view.py
  - Selection panel: `ImageShape` field table (X, Y, W, H, rotation like rect) and a read-only line "{w} × {h} px, {ppi} PPI"; style editor limited to opacity for images
  - Layers panel: lazy thumbnail per image row cached by `(digest, size)` (rendered with the decode cache, never on every refresh), reference marker; show/hide references passed to `draw_document(references=...)` and refreshed idempotently
  - Reference images locked on creation and not picked by canvas clicks, selectable in the Layers panel
  - Purpose: images are understandable and editable in the panels (Req 4.3, 4.8)
  - _Leverage: `_FIELDS` tables in `selection_view`, `object_tree_model`, `refresh(state)` idempotency rules_
  - _Requirements: 4.2, 4.3, 4.5, 4.8_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python/PySide6 developer | Task: Implement design.md panel changes; `refresh` stays cheap and idempotent with `blockSignals`, thumbnails generated lazily; run `uv run python scripts/update_translations.py` and translate in `de.po` | Restrictions: no rebuild of a widget from inside its own signal (use `QTimer.singleShot`), no Qt below views | Success: ruff + pytest green; `scripts/screenshot_app.py` with a demo image shows panel line, thumbnail, dimmed reference (read the PNG, delete scratch crops). Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 12. Conformance baseline, self-test, benchmark, docs
  - Files: tests/scripts/svg_conformance_pass.txt, docs/svg-conformance.md, docs/file-format.md, main.py/presstoshape/app.py (`--self-test`), scripts/bench_canvas.py, .spec-workflow/steering/product.md, .spec-workflow/steering/tech.md, README.md
  - Run `svg_conformance.py fetch` and `report`; add every matching `struct-image-*`, `struct-symbol-01-b`, `coords-viewattr-02-b`, `coords-viewattr-04-f`, `masking-path-04-b/-06-b/-07-b/-11-b` after comparing by eye; keep reviewed mismatches as `!name # reason`; nothing leaves the pass list; target ≥ 15 matching image-related cases
  - `--self-test` decodes tiny PNG, JPEG and WebP; `bench_canvas.py` gains 200 mid-size images (CPU and GL), costs recorded in the log
  - Regenerate `docs/svg-conformance.md`; update steering product/tech import-gap and feature lists; hedge README/FAQ wording on images; log a note for the maintainer to tick Level 5 and editor P1 "Import images" in the local `FEATURE_GAPS.md` (not in the repo)
  - Purpose: numbers and docs reflect the level (Req 8)
  - _Leverage: `scripts/svg_conformance.py`, `tests/scripts/svg_conformance_pass.txt`, `scripts/bench_canvas.py`_
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md testing/baseline items; compare each candidate test image with ours by eye before adding | Restrictions: never drop a pass-list entry to make a change pass without saying so; no claims in README beyond what is tested | Success: pytest with suite fetched green, report regenerated, self-test passes from source. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 13. End-to-end check and cleanup
  - Files: scratch scripts only (scratchpad), plus fixes in any touched file
  - Headless `QTest` script on `canvas.viewport()`: Place via dialog slot, drop an image file, paste a bitmap, Shift drag-scale, rotate, Replace, Make Reference, toggle Show References, undo each step; once offscreen (raster), once on the desktop (GL)
  - Round trip: open SVG with images → edit → save `.p2s` → reopen → save SVG → reopen; recovery snapshot with a large image does not block the UI longer than a frame (measure; move the write off the UI thread if it does and say so)
  - `uv run ruff check .`, `uv run ruff format .`, full `uv run pytest`, `uv run python main.py --self-test`; update_translations clean; delete scratch files
  - Purpose: the level works as a whole (Req 3–8, Non-functional)
  - _Leverage: `PySide6.QtTest.QTest`, `scripts/screenshot_app.py`, `scripts/bench_canvas.py`_
  - _Requirements: All_
  - _Prompt: Implement the task for spec svg-conformance-level5, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Senior Python developer | Task: Run the end-to-end checks from design.md "End-to-End Testing" and fix anything found in the owning module with a test | Restrictions: do not weaken tests; do not start long-running servers; report faithfully what failed | Success: all checks pass, findings and measurements recorded in the final task log. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
