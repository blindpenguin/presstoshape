# Tasks Document

Every task that adds an import note runs `uv run python scripts/update_translations.py` and translates the new entries in `de.po` (tests fail otherwise). Every task ends with the full `uv run pytest` green, with the W3C suite fetched, so no pass-list entry regresses.

- [x] 1. Path data and point lists up to the first error
  - Files: presstoshape/formats/svg_values.py, presstoshape/formats/svg_reader.py, presstoshape/formats/svg_notes.py, presstoshape/assets/translations/*, tests/formats/test_svg_values.py (new or existing), tests/formats/test_svg_import.py
  - Before changing anything: write a scratch benchmark (scratchpad, not committed) that generates a 10,000-shape SVG with a 200-rule style sheet (classes plus a few descendant selectors) and times `read_svg_with_notes`; record the baseline in this task's log
  - `valid_path_prefix`, `parse_path_data` returning (segments, cut), `parse_points`; reader keeps prefixes, drops empty ones, counts `Note.PATH_ERROR`
  - Purpose: one broken path no longer blocks a file (Req 1.1, 1.2, 1.5, 1.6)
  - _Leverage: svgelements path parsing on the validated prefix, NoteCollector_
  - _Requirements: 1.1, 1.2, 1.5, 1.6, 1.7 (paths-data-20-f)_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced with parsers | Task: Implement design.md component 1 and the PATH_ERROR note; tests as listed in design "Unit Testing" for valid_path_prefix and points, plus a reader test where one broken path among valid shapes still opens with the note, and a mocked svgelements failure on a valid prefix | Restrictions: single-pass scanner, no backtracking regex; parse_path_data's callers all updated; no Qt | Success: tests green, paths-data-20-f opens and matches by eye. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Lengths with units and the root viewport
  - Files: presstoshape/formats/svg_lengths.py (new), presstoshape/formats/svg_reader.py, presstoshape/formats/svg_values.py, tests/formats/test_svg_lengths.py (new), tests/formats/test_svg_import.py
  - `Viewport`, `parse`, `resolve`, `length`; reader gets a `Viewport` from the root (viewBox, else width/height, else 100 × 100); geometry attributes, text x/y/dy and `<use>` x/y through `length` with their axis and font size; `font-size` resolved to user units after the cascade (em/% against the parent); stroke width, dashes and dash offset resolved with axis "other"; invalid geometry values counted as `Note.INVALID_VALUE` (add the note here)
  - Purpose: correct sizes in every unit (Req 2, 1.3 for geometry)
  - _Leverage: svg_page.read_page for the viewBox, existing corner_radii rules_
  - _Requirements: 1.3, 2.1–2.4_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md components 2 and 7 and the font-size resolution of component 6; replace parse_length/font_relative_length uses in the reader with svg_lengths (keep helpers only where still used elsewhere, e.g. svg_page, or move those callers too); tests per design "Unit Testing" for svg_lengths plus reader tests for % per axis, em chains through nested groups, ex, invalid attribute length counted | Restrictions: absolute unit factors must equal today's; svg_page's physical size reading stays correct (its tests unchanged); no Qt | Success: tests green, coords-units-02-b matches by eye. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Property validation, `color` and `currentColor`
  - Files: presstoshape/formats/svg_properties.py (new), presstoshape/formats/svg_reader.py, tests/formats/test_svg_properties.py (new), tests/formats/test_svg_import.py
  - `normalize(name, value, css)`; `_Reader.style` passes attribute values with css=False and sheet/inline values with css=True, skips and counts invalid ones; `color` inherited and computed (`currentColor`/`inherit` → parent's); `_paint` resolves `currentColor` with the element's own colour, alpha multiplied like other colours; system colours invalid
  - Purpose: invalid values ignored instead of guessed; currentColor works with SVG 2 inheritance (Req 1.3, 3, 4.5)
  - _Leverage: svgelements colour parsing (`_color`), existing `_assign` inherit handling_
  - _Requirements: 1.3, 1.5, 3.1–3.6, 4.5_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer familiar with the CSS cascade | Task: Implement design.md components 3 and the colour parts of 6; tests per design for svg_properties plus reader tests: currentColor on nested groups where a child sets its own color (SVG 2 result), color: inherit/currentColor, rgba colour alpha, `stroke-width="10PX"` attribute ignored but `stroke-width: 20PX` in CSS valid, system colour ignored | Restrictions: keep the cascade order of today (attribute < sheet < inline < !important); no behaviour change for valid values; no Qt | Success: tests green; painting-fill-02-t, struct-group-03-t, types-basic-02-f match by eye. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. CSS selectors, `<style>` filtering and `@media`
  - Files: presstoshape/formats/css_selectors.py (new), presstoshape/formats/css.py, presstoshape/formats/svg_reader.py, tests/formats/test_css_selectors.py (new), tests/formats/test_css.py, tests/formats/test_svg_import.py
  - `Compound`, `Selector`, `parse_selector`, `Node` protocol; reader's lazy node view (parent, siblings, index, inherited language); `Stylesheet` indexed by rightmost compound, `declarations_for(node)`; `css.parse` enters `@media` all/screen; reader uses only `<style>` with CSS type and all/screen media
  - Purpose: style sheets applied as browsers apply them (Req 4)
  - _Leverage: existing css.parse block/declaration parsing and index idea_
  - _Requirements: 4.1–4.4, 4.6, 4.7_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with CSS selector engine experience | Task: Implement design.md component 4; tests per design "Unit Testing" for css_selectors (each combinator, attribute operator, pseudo-class, :not, :nth-child formulas, specificity, pseudo-elements rejected, a 10,000-character adversarial selector parses quickly) and css (@media handling, skipped counts), reader tests for `<style type="text/foo">` ignored and a realistic exported sheet; run the task-1 benchmark and record the time | Restrictions: existing test_css behaviour kept unless the requirement changes it; opening time within 10 % of the baseline; no Qt | Success: tests green, benchmark within budget; styling-css-02-b/-03-b/-04-f/-10-f, styling-elem-01-b, struct-use-10-f/-11-f checked by eye. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Conditional processing and the user's languages
  - Files: presstoshape/formats/svg_conditions.py (new), presstoshape/formats/svg_reader.py, presstoshape/formats/svg_notes.py, presstoshape/editing/operations/documents.py, presstoshape/editing/operations/clipboard.py, presstoshape/assets/translations/*, tests/formats/test_svg_conditions.py (new), tests/formats/test_svg_import.py, tests/editing/* (where open/paste are tested)
  - `passes`, `switch_choice`; reader checks conditions on every element incl. `<use>` targets and symbol content, `<switch>` draws only its choice, `Note.CONDITIONAL` counted; `read_svg_with_notes(text, languages=("en",))`, `read_shapes_svg(text, languages=("en",))`; editing passes `(i18n.active_language(), "en")`
  - Purpose: the alternative a browser shows, in the user's language (Req 5)
  - _Leverage: i18n.active_language, existing visit/use code_
  - _Requirements: 5.1–5.8_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 5; tests per design for svg_conditions plus reader tests (switch with de/en/fallback children under languages ("de", "en") and ("fr", "en"), requiredExtensions false, requiredFeatures ignored, systemLanguage on a `<use>` target) and an editing test that opening passes the active language | Restrictions: formats/ gets languages only as a parameter; no Qt below views | Success: tests green; struct-cond-* checked by eye against the requirement. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. Text whitespace and `xml:space` on save
  - Files: presstoshape/formats/svg_values.py, presstoshape/formats/svg_reader.py, presstoshape/formats/svg.py, tests/formats/test_svg_import.py, tests/formats/test_svg.py
  - `Whitespace` builder; `_collect_runs` hands each text node its inherited `xml:space`; writer sets `xml:space="preserve"` on text with leading, trailing or repeated spaces
  - Purpose: spaces come out as meant, in and out (Req 6)
  - _Leverage: existing _TextRun/_collect_runs, collapse_whitespace (replaced)_
  - _Requirements: 6.1–6.6_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md components 8 and 9; tests: default rules (newline removed, tab → space, collapse, trim), preserve rules, mixed modes across tspans without lost or doubled spaces at boundaries, writer output with and without xml:space, round trip of "  two  spaces " unchanged, clipboard SVG round trip | Restrictions: SVG written for texts without special spaces stays byte-identical; no Qt | Success: tests green; text-ws-02-t and -03-t checked by eye. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Notes for uneven strokes and skewed text
  - Files: presstoshape/formats/svg_reader.py, presstoshape/formats/svg_notes.py, presstoshape/assets/translations/*, tests/formats/test_svg_import.py
  - Similarity check on the matrix; `Note.UNEVEN_STROKE` in `_paint` for stroked shapes, `Note.TEXT_SKEW` in `_text`
  - Purpose: approximations are reported (Req 7)
  - _Leverage: existing _paint scale, transform_shape behaviour for text_
  - _Requirements: 7.1–7.3_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 10; tests: scale(8,2) stroked path noted, same unstroked not noted, uniform scale and mirror (scale(-1,1), rotation) not noted, skewX text noted, rotated text not | Restrictions: no change to the approximation itself | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. Pass-list entries checked against resvg
  - Files: scripts/svg_conformance.py, tests/scripts/test_svg_conformance.py
  - `PassEntry.reference`; `~name [threshold] # reason`; `check_test(..., reference)`; `check_suite` and pytest use the entry's reference; report shows the reason
  - Purpose: tests with outdated references can guard the code (Req 8)
  - _Leverage: render_resvg, existing `!` entry handling_
  - _Requirements: 8.1–8.3_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md component 12; offline tests: parsing `~` entries (reason required, threshold allowed, duplicates with other forms refused), check_test against resvg on the fake suite, report row shows the reason | Restrictions: existing entries and behaviour unchanged | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Pass list, baseline and performance check
  - Files: tests/scripts/svg_conformance_pass.txt, docs/svg-conformance.md, FEATURE_GAPS.md (not committed)
  - Run the report; check every new candidate by eye; add passing tests, turn fixed `!` entries into normal ones, add `~` entries (`styling-pres-03-f`, `text-ws-01-t`) and new reviewed exceptions with reasons (`color-prop-05-t`, `color-prop-04-t`, `paths-data-18-f`, tests needing Level 2 or fonts); regenerate the summary; final benchmark against the task-1 baseline; tick Level 1 in the feature gap list
  - Purpose: record and guard the level's progress (Req 9)
  - _Leverage: report candidates and sheets, scratch grid script approach from Level 0_
  - _Requirements: 9.1–9.3, NFR performance_
  - _Prompt: Implement the task for spec svg-conformance-level1, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Test engineer with an eye for rendering detail | Task: Curate as in Level 0 (match by score is not enough; exclude accidental matches); no entry from before this level may leave the list; generate docs/svg-conformance.md; report before/after in-scope numbers and the benchmark | Restrictions: do not change presstoshape/ in this task — if curation finds a bug, record it as a reviewed exception and report it | Success: full pytest green with the suite fetched, report shows no regressions, summary regenerated. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
