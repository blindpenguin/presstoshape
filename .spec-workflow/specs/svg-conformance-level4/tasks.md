# Tasks Document

Every task that adds an import note or UI text runs `uv run python scripts/update_translations.py` and translates the new entries in `de.po` (tests fail otherwise). Every task ends with `uv run ruff check .`, `uv run ruff format .` and the full `uv run pytest` green with the W3C suite fetched, so no pass-list entry regresses. Until task 6 the reader still ignores `clip-path` / `mask`; tasks 1–5 must not change what any existing file looks like. A masked group never exists before task 6 or task 9, so every earlier task builds its own masked groups in tests.

- [x] 1. Masking model and sanitising
  - Files: presstoshape/models/shapes.py, tests/models/test_masking.py (new)
  - `MaskType`, frozen `Masking(type, mask_ids, inverted=False, region=None)` with `is_mask`, `GroupShape.masking`, helpers `mask_children(group)` / `content_children(group)`; `sanitized` fixes masking (unknown type → `clip`, `mask_ids` pruned to existing children and deduplicated, bad `region` → `None`); `with_children` in `editing/containers.py` prunes `mask_ids` when children disappear
  - Purpose: the value type every later task builds on (Req 1)
  - _Leverage: `GroupShape`, `children_of`, `sanitized`, `containers.with_children`_
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 1 with the unit tests listed under "Unit Testing" for models (construction, equality, hash, every sanitising rule, helpers, pruning in `with_children`, nesting of masked groups) | Restrictions: frozen dataclasses, no Qt/skia, `region` is a plain 4-tuple, existing tests unchanged, no behaviour change for groups without masking | Success: tests green, nothing else changes behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Clip and mask rendering
  - Files: presstoshape/render/masks.py (new), presstoshape/render/paths.py, presstoshape/render/scene.py, tests/render/test_masks.py (new)
  - `mask_clip_path(group, cache)` (union of mask-object fill outlines with fill rule, inverted via big rect subtract), `PathCache` clip entries (cached, pruned) and masked-group bounds (clip: content ∩ clip, mask types: content ∩ region), `_draw_group` clip path and the two-layer luminance/alpha mask with `kDstIn`; entered masked group draws all children plainly plus a dashed outline of the mask objects (`CanvasColors.mask_outline`)
  - Purpose: masked groups draw on canvas and in PNG export, cached per group (Req 3.1–3.6, 3.8, 3.9)
  - _Leverage: `PathCache` validity scheme, `geometry.booleans.combine_parts`, `transforms.area_outline`, `draw_shape`, `render/gradients.py`_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.8, 3.9, 3.10_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with Skia experience | Task: Implement design.md component 3 (except hit-testing) with CPU-surface pixel tests per "Unit Testing" (nonzero/evenodd, two-child union, nested clip, transformed mask, inverted clip, luminance white/black/gradient/50% alpha, stroke in mask, region cut, alpha type, empty clip and empty mask, masked group with opacity, masked group inside a masked group, bounds of masked groups, cache identity and invalidation, entered state draws unmasked); before changing anything run `scripts/bench_canvas.py` (no masks) and record the baseline in this task's log | Restrictions: no clip geometry built per frame; unmasked content costs exactly what it does today; a layer only where a mask requires it; guard pathops failures with the fallback from design "Error Scenarios" 6; no Qt in render (colour passed in via `CanvasColors`) | Success: tests green, benchmark without masks unchanged. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Hit-testing, framing and snapping of masked groups
  - Files: presstoshape/render/hit_test.py, presstoshape/render/handles.py, presstoshape/tools/snapper.py, presstoshape/render/paths.py, tests/render/test_hit_test.py
  - Masked group (not entered) is picked only on its visible content: content regions ∩ clip path (clip type) or content regions (mask types); mask objects never hit, framed, snapped to or aligned unless the group is entered; selection frame uses visible bounds
  - Purpose: a masked group behaves as one object with its visible outline (Req 3.7, 5.7)
  - _Leverage: `_regions` / `_contains`, `PathCache.geometry_bounds`, `mask_children` / `content_children`_
  - _Requirements: 3.7, 5.7_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md "Hit-test" and "Bounds" paragraphs with tests: click outside the clip misses, inside hits, a mask object alone is never hit, entered state picks mask objects and content, marquee and snap targets ignore mask objects, frame equals visible bounds | Restrictions: intersect regions once and cache them with the clip in `PathCache`, no per-click pathops over unrelated shapes | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. `.p2s` version 9
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, tests/formats/test_p2s.py, tests/formats/samples/v9.p2s (new), docs/file-format.md
  - Group object gains optional `masking` (`type`, `mask` child ids, `inverted`, `region`); `CURRENT_VERSION` 9; `MIGRATIONS[8]` no-op; sample with clip, luminance and alpha; docs row and object description
  - Purpose: masks survive save/open and copy/paste (Req 4.4, 4.5, 4.6)
  - _Leverage: group encode/decode, `_field`, `_optional_number`, `_damaged`, existing sample/migration tests, `formats/clipboard.py`_
  - _Requirements: 4.4, 4.5, 4.6_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 5 with tests: round trip of each mask type, inverted, region, nested masked groups; defaults omitted; ids not among the children, unknown type and bad region rejected with a path in the message; v8 sample still opens, v9 sample opens; clipboard payload round trip keeps masking | Restrictions: explicit encoders/decoders, never generic over dataclass fields; files without masks byte-identical to today's output apart from the version number | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. SVG writer
  - Files: presstoshape/formats/svg_mask_defs.py (new), presstoshape/formats/svg.py, presstoshape/formats/svg_notes.py, tests/formats/test_svg_mask_defs.py (new), tests/formats/test_svg_generator.py
  - `MaskDefs` (ids from the shared counter, `<clipPath>` / `<mask>` into the shared `<defs>`, `clip-path` / `mask` attribute on a `<g>`), clip-rule per object, nested masked groups in a clip flattened by pathops intersection, inverted clip as rect + geometry with evenodd, mask region, `mask-type` alpha, inverted opacity mask saved non-inverted with a save-report note; resvg generator check
  - Purpose: saved SVG contains the clips and masks and renders like the canvas (Req 4.1–4.3)
  - _Leverage: `PaintDefs` pattern from `svg_paint.py`, `_untransformed_element`, `combine_parts`, `svg_page.number_text`, existing generator-check helpers_
  - _Requirements: 4.1, 4.2, 4.3_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 4 with tests per "Unit Testing" (id stability between saves, clip-rule, no paint on clip children, nested clip flattening, inverted clip, luminance with gradient, alpha type, region, group opacity plus mask on one `<g>`, Composite and text inside masks) and extend the resvg generator check with built documents for each render case from task 2 | Restrictions: files without masks byte-identical to today's output; masked groups always written as `<g>` | Success: tests green incl. resvg comparison. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. Reader: clip paths and masks
  - Files: presstoshape/formats/svg_masks.py (new), presstoshape/formats/svg_reader.py, presstoshape/formats/svg_notes.py, tests/formats/test_svg_masks.py (new)
  - `resolve_clip` / `resolve_mask` with clip style (black fill, no stroke, `clip-rule`, `visibility` ignored, `display:none` skipped), units (`clipPathUnits`, `maskUnits`, `maskContentUnits`) baked into the mask shapes with the content's bbox, `transform` on `<clipPath>`, nested `clip-path` on children and on the clipPath, mask region, `mask-type`, memoised definitions copied with fresh ids, cycle/depth/count caps; the element wrapper in `svg_reader.py` builds the masked group (clip outside, mask inside); reworded and new notes
  - Purpose: files with clip paths and masks open as editable masked groups (Req 2)
  - _Leverage: `_Reader.ids`, `_Reader.style`, `<use>` resolution, `Viewport` stack, `svg_gradients.py` as the structural template, `geometry.transforms.outline` + `segments_bounds`, `transform_shape`_
  - _Requirements: 2.1–2.10_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with SVG knowledge | Task: Implement design.md component 2 with the reader unit tests listed in "Unit Testing" (every rule of requirement 2, `masking-path-14-f` non-inheritance, missing/wrong-type/cyclic references, empty clip and empty mask, objectBoundingBox on an empty box, shared clipPath gets fresh ids per use, hostile inputs: 10 000 children, 100-deep nesting, NaN); the module takes callables from the reader and imports neither the reader nor Qt/skia | Restrictions: never raise out of the reader; no value from a file reaches the model unsanitised; no copied code from other editors (format facts only) | Success: tests green; `masking-*` report counts recorded in the task log. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Operations: make, release, invert, type, move between sides
  - Files: presstoshape/editing/operations/masks.py (new), presstoshape/editing/operations/__init__.py, presstoshape/editing/operations/groups.py, presstoshape/editing/operations/booleans.py, presstoshape/editing/operations/style.py, tests/editing/test_masks.py (new)
  - `object.clip.make`, `object.clip.release`, `object.mask.make`, `object.mask.release`, `object.mask.invert` (checked callback), `object.mask.type`, `object.mask.to_mask`, `object.mask.to_content`; Ungroup on a masked group releases it; booleans/divide/Composite refuse masked groups with a status message; `restyle_shape` recurses into content only
  - Purpose: the editor feature (Req 5.1–5.3, 5.5–5.8)
  - _Leverage: `groups.group` / `ungroup`, `containers.change_container`, `queries.selected_shapes`, `@operation`, `session.edit`, `new_id`_
  - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 5.7, 5.8_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 6 with tests: each operation positive case and each refusal (different containers, one object, nothing masked), undo/redo labels, selection afterwards, released clip objects without paint get the thin default stroke, released opacity mask objects become hidden, nesting is kept, Make inside an entered container, to_mask/to_content, ungroup release, boolean refusal, delete-all-children removes the group, `edit_path` interaction; `can_run` for every operation | Restrictions: operations are plain functions, one undo step each, no shortcuts here (task 9), UI texts through `_`/`N_`/`ngettext`/`pgettext` and `de.po` complete | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. Tree data and names for masked groups
  - Files: presstoshape/editing/object_tree.py, presstoshape/views/edit_bar_view.py, presstoshape/views/selection_view.py, tests/editing/test_object_tree.py
  - Row type `clip` / `mask` for masked groups, child `role` (`mask` / `content`), labels "Clipping Mask" / "Opacity Mask", edit bar names, selection panel type name and visible-bounds fields
  - Purpose: the UI can tell masked groups and their two sides apart (Req 5.4, 5.9)
  - _Leverage: `object_type`, `object_label`, `_TYPE_NAMES` tables in the views_
  - _Requirements: 5.4, 5.9_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 7 data side with tests for `object_tree` rows and labels | Restrictions: Qt only in the two view files; views stay small, state passed in explicitly | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Menus, icons, Layers rows and canvas overlay colour
  - Files: presstoshape/views/keymap.py, presstoshape/views/actions.py, presstoshape/views/layers_panel.py, presstoshape/views/theme.py, presstoshape/views/canvas_view.py, scripts/generate_icons.py, presstoshape/icons.py, presstoshape/assets/icons/*.svg, presstoshape/assets/translations/*
  - Object → Clipping Mask → Make / Release, Object → Opacity Mask → Make / Release / Invert / Type; context-menu entries for move to mask / content; Layers panel rows with mask icon and badge, mask objects first; `CanvasColors.mask_outline`; no shortcuts unless the user chose one when reviewing this task list
  - Purpose: the feature is reachable and visible (Req 5.1, 5.4, 5.9)
  - _Leverage: `keymap` layouts, `actions.py` builders, `SvgIconEngine`, `generate_icons.py` mapping, `LayersPanel` row builders_
  - _Requirements: 5.1, 5.4, 5.9_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Wire the operations from task 7 into menus and the Layers panel as in design.md component 6 "Keymap/menus" and component 7; regenerate icons with `uv run --group dev python scripts/generate_icons.py`; run `scripts/update_translations.py`, translate `de.po`, check mnemonics; capture `uv run python scripts/screenshot_app.py` with a masked group (Layers rows, entered overlay) and read it | Restrictions: connect `triggered` through lambdas, defer widget rebuilds from item signals with `QTimer.singleShot(0, ...)`, `refresh(state)` idempotent and cheap, no QIcon(path) | Success: translation and architecture tests green, screenshot checked, scratch crops deleted. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 10. Interaction check in the real window
  - Files: scratch script only (not committed), notes in the task log
  - Drive the window with `QTest` offscreen (raster) and on the desktop (GL): draw two shapes, Make Clipping Mask, enter, move the mask, leave, Release, undo ×3; the same for an opacity mask with a gradient; copy/paste and save/reopen a masked group in `.p2s` and SVG
  - Purpose: confirm the feature works end to end, not only in unit tests (design "End-to-End Testing")
  - _Leverage: `canvas._vp.to_screen`, `scripts/screenshot_app.py`, `tests/helpers.ToolDriver`_
  - _Requirements: 3, 4, 5_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: QA engineer | Task: Run the interaction scenarios from design.md "End-to-End Testing" in a scratch script under the scratchpad, fix defects found in the code that caused them (with a test each), and run `scripts/bench_canvas.py` with 1000 masked groups (clip and luminance) recording the numbers in the log | Restrictions: no whole-window pixel assertions in the pytest suite, delete scratch files | Success: scenarios pass on both renderers, benchmark recorded (no regression for unmasked content; masked within 2× of unmasked per object). Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 11. Conformance baseline and docs
  - Files: tests/scripts/svg_conformance_pass.txt, docs/svg-conformance.md, .spec-workflow/steering/product.md, .spec-workflow/steering/tech.md
  - Fetch the suite, run `report --filter 'masking-*'`, compare each match by eye, add to the pass list; re-evaluate `!masking-path-12-f`; keep `masking-filter-01-f` with a "filters level" reason; re-run struct and painting tests that failed only because of clip/mask; regenerate `docs/svg-conformance.md` with `--write-summary`; update the import-gap lines in the steering docs
  - Purpose: updated baseline (Req 6)
  - _Leverage: `scripts/svg_conformance.py`, the existing pass list format_
  - _Requirements: 6.1–6.5_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: QA engineer | Task: Update the baseline as in requirement 6; read each report image next to its reference before adding a test; target at least 15 of 19 `masking` tests matching, the rest with `!name # reason` | Restrictions: no entry leaves the pass list; never add a test without comparing it by eye; say in the log if any previously passing test needed attention | Success: `uv run pytest` green with the suite fetched, summary regenerated, numbers recorded in the log. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 12. Final cleanup
  - Files: whole change
  - `uv run ruff check .`, `uv run ruff format .`, `uv run pytest`, `uv run python main.py --self-test`; check no scratch files, `dev-screenshots/` untouched in git, comments only where a non-obvious why; open questions from the design answered and recorded
  - Purpose: ready to commit (Req all)
  - _Leverage: project checks in CLAUDE.md_
  - _Requirements: All_
  - _Prompt: Implement the task for spec svg-conformance-level4, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Senior developer | Task: Final pass over the diff: dead code, comment density, naming rules from the user's memory (type not kind, speaking variable names), translations complete, docs consistent | Restrictions: do not commit; report results faithfully | Success: all checks green and reported. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
