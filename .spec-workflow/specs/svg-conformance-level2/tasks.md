# Tasks Document

Every task that adds an import note runs `uv run python scripts/update_translations.py` and translates the new entries in `de.po` (tests fail otherwise). Every task ends with the full `uv run pytest` green, with the W3C suite fetched, so no pass-list entry regresses.

- [x] 1. viewBox, `preserveAspectRatio` and overflow maths
  - Files: presstoshape/formats/svg_viewport.py (new), tests/formats/test_svg_viewport.py (new)
  - `parse_view_box`, `Aspect`, `DEFAULT`, `parse_aspect`, `fit`, `escapes`; an `INVALID` sentinel distinct from `None` (absent)
  - Purpose: one pure unit for every viewport caller (Req 1.2, 2.1–2.4, 4.3)
  - _Leverage: svg_lengths strict-parse style, geometry.affine, geometry.transforms.outline_
  - _Requirements: 1.2, 2.1–2.5, 4.1, 4.3_
  - _Prompt: Implement the task for spec svg-conformance-level2, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with geometry experience | Task: Implement design.md component 1 with tests per "Unit Testing" (all nine aligns × meet/slice, none, defer, case sensitivity, junk, hand-computed matrices for wide and tall viewports, non-finite numbers, escapes for inside/outside/group/rotation/tolerance/text ignored); before changing anything write a scratch benchmark (scratchpad, not committed) that times read_svg_with_notes on a generated 10,000-shape SVG and record the baseline in this task's log | Restrictions: pure, no Qt, no reader imports, single-pass tokeniser (no backtracking regex), results always finite | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Nested `<svg>`, shared viewport matrix and `<use>` of `<svg>`
  - Files: presstoshape/formats/svg_reader.py, presstoshape/formats/svg_properties.py, presstoshape/formats/svg_notes.py, presstoshape/assets/translations/*, tests/formats/test_svg_import.py, tests/formats/test_svg_properties.py
  - `_View`, `_viewport`, `_nested_svg`, `_check_overflow`; delete `_symbol_matrix`; `_use` sends `symbol` and `svg` targets through `_viewport`; `self.viewport` swapped around nested content; `overflow` property validated; `Note.VIEWPORT_OVERFLOW` added, `Note.NESTED_SVG` removed
  - Purpose: nested content appears; symbols share the maths; overflow reported (Req 1, 2.6, 4, 5.3)
  - _Leverage: _group, _use, svg_viewport, NoteCollector_
  - _Requirements: 1.1–1.8, 2.4, 2.6, 4.1–4.5, 5.1, 5.3_
  - _Prompt: Implement the task for spec svg-conformance-level2, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md components 2 and 4; reader tests per "Integration Testing" (x/y/viewBox/par placement, two-deep nesting, % inside a nested viewport, use of svg with width/height override, symbol regression cases kept, zero/negative sizes skip, opacity and systemLanguage through nested svg, overflow note noted / not noted / overflow=visible / symbol use, invalid viewBox and preserveAspectRatio counted, non-finite values never raise, no NESTED_SVG note) | Restrictions: svg_lengths.Viewport restored in finally; no behaviour change for files without nested viewports; no Qt | Success: tests green; struct-group-02-b, struct-svg-03-f, styling-css-08-f render with content (checked in task 4). Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Root viewport fit
  - Files: presstoshape/formats/svg_page.py, presstoshape/formats/svg_reader.py, tests/formats/test_svg_page.py, tests/formats/test_svg_import.py
  - `Page.view`; `read_page` fits when width/height are absolute, positive, differ in proportion by more than 0.1 % from a valid viewBox and the file has no PressToShape unit/DPI attributes; `read_svg_with_notes` uses `page.view` as base matrix; invalid root `preserveAspectRatio` counted; `read_shapes_svg` unchanged
  - Purpose: page keeps the author's size and placement (Req 3)
  - _Leverage: svg_page._css_px/_inches, svg_viewport.fit_
  - _Requirements: 3.1–3.5_
  - _Prompt: Implement the task for spec svg-conformance-level2, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 3; tests: width=200 height=100 viewBox 0 0 100 100 opens 200 × 100 centred (xMidYMid meet), stretched with none, slice; equal proportions and % / missing sizes unchanged; PressToShape's own files byte-identical on save→open→save; mm-based Inkscape files unchanged | Restrictions: existing svg_page tests unchanged; no Qt | Success: tests green; struct-frag-02-t, -05-t, -06-t stay on the pass list. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Round trips, generator check and pass list
  - Files: tests/formats/test_svg.py, tests/formats/test_svg_generator.py, tests/scripts/svg_conformance_pass.txt, docs/svg-conformance.md, FEATURE_GAPS.md (not committed)
  - Round trip tests for a nested-`<svg>` file (SVG and .p2s); run the report, check every new candidate by eye (`struct-group-02-b`, `struct-svg-01-f`, `-02-f`, `-03-f`, `styling-css-08-f`, `struct-use-08-b`, `struct-symbol-01-b`, `struct-use-09-b`, `coords-viewattr-01-b`, `-03-b`); add passing tests, turn fixed `!` entries into normal ones, re-annotate the rest (`viewport overflow clip missing (Level 4)`, images Level 5); regenerate the summary; final benchmark against the task-1 baseline; tick Level 2 items in the feature gap list (overflow stays open)
  - Purpose: record and guard the level's progress (Req 5, 6)
  - _Leverage: report candidates and sheets, curation approach from Levels 0 and 1_
  - _Requirements: 5.1–5.3, 6.1–6.3, NFR performance_
  - _Prompt: Implement the task for spec svg-conformance-level2, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Test engineer with an eye for rendering detail | Task: Curate as in Levels 0 and 1 (score alone is not enough; exclude accidental matches such as struct-svg-02-f before this level); no entry from before this level may leave the list; report before/after in-scope numbers and the benchmark | Restrictions: do not change presstoshape/ in this task — if curation finds a bug, record it as a reviewed exception and report it | Success: full pytest green with the suite fetched, report shows no regressions, summary regenerated. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
