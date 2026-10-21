# Requirements Document

## Introduction

PressToShape is going to climb towards W3C SVG conformance step by step (feature gap list, "SVG conformance", Levels 0–8). Every later step needs a way to see where we stand and to notice when something that worked breaks again. Today there is none: a one-off probe against the W3C SVG 1.1 (Second Edition) test suite showed that 524 of 525 test files open, all of those survive save → reopen, and 269 render close to the reference images, but nothing records those numbers or protects them.

This spec is Level 0, measurement only. It adds:

- **The test suite on demand**: a developer script fetches the pinned W3C SVG 1.1 suite into a local cache. Nothing of the suite is committed.
- **A conformance report**: every test opened, saved, reopened and rendered by PressToShape, compared with the W3C reference image, summarised per chapter, with side-by-side images of the differences.
- **A curated pass list**: the tests known to look right, checked in and guarded by pytest, so a regression fails the test suite.
- **A generator check**: SVG files written by PressToShape are rendered by an independent renderer (**resvg**, the most complete static SVG renderer available as a library) and must look like they do on our canvas.

No reader, writer or renderer behaviour changes in this spec. Fixes start with Level 1.

## Alignment with Product Vision

- **Success metric, Interop**: "common Inkscape and Illustrator-exported SVG files open correctly" and "PressToShape-made SVG round-trips … intact" become measurable instead of anecdotal.
- **Principle 4**: "features SVG can't express degrade predictably … instead of silently disappearing". The report lists, per test, what the import notes said, so silent losses show up as differences without a note.
- **Principle 5, Inkscape interop**: the generator check makes sure what we write is read the same by another renderer, not only by ourselves.
- **Tech steering, Security**: files are untrusted input. The suite download is verified and extracted safely; the app itself stays offline (only a developer script touches the network).

## Requirements

### Requirement 1: Fetch the W3C test suite

**User Story:** As a developer, I want one command that gets the W3C SVG 1.1 test suite onto my machine, so that I can run the conformance checks without hunting for files.

#### Acceptance Criteria

1. WHEN the developer runs the fetch command THEN the script SHALL download the W3C SVG 1.1 Second Edition test suite archive from its pinned URL, verify it against a pinned SHA-256, and extract it into a gitignored cache folder inside the repository.
2. IF the checksum does not match THEN the script SHALL delete the download, extract nothing and exit with an error naming expected and actual checksum.
3. WHEN the suite is already in the cache with the expected checksum THEN the fetch command SHALL do nothing and say so.
4. Extraction SHALL refuse archive members that would land outside the cache folder (absolute paths, `..`, links pointing outside).
5. The PressToShape application SHALL NOT download, read or depend on the suite; it is a developer resource only.

### Requirement 2: Conformance report

**User Story:** As a developer, I want a report of how every W3C test opens and renders in PressToShape, so that I can see which areas are good, which are broken, and what a change improved.

#### Acceptance Criteria

1. WHEN the developer runs the report command THEN the script SHALL, for every test file in the suite (or the subset selected by a name pattern):
   - open it with PressToShape's SVG reader, recording an error message instead of stopping when reading fails;
   - record the import notes;
   - save it as SVG and open that again, recording whether this works;
   - render the opened document with PressToShape's PNG export at the reference image size and compare it with the W3C reference image.
2. The comparison SHALL give each test a **difference score** (share of pixels that differ noticeably, after both images are composited on white and softened enough that anti-aliasing and small glyph differences don't count) and a status: **match** (score below a threshold, 3 % to begin with), **differs**, or **error**.
3. The report SHALL summarise per chapter (the test name prefix, e.g. `shapes`, `pservers`) and sub-chapter (e.g. `pservers-grad`): number of tests, matches, differences, errors.
4. The report SHALL mark chapters outside our target (animation, scripting, DOM, interactivity, SVG fonts, colour profiles, extensibility; see the feature gap list's non-goals) as **out of scope** and leave them out of the totals.
5. The report SHALL list, per test: status, score, import notes and the reading or round-trip error if any.
6. The report SHALL include a side-by-side image (PressToShape | W3C reference | resvg rendering of the original file) for every test that is not a match, so a developer can judge it by eye. The resvg column helps to spot outdated reference images.
7. The report SHALL list **candidates**: in-scope tests that match but are not on the pass list, and tests on the pass list that no longer match.
8. Report output SHALL go to a gitignored folder; running the report SHALL NOT change any committed file unless the developer asks for the summary to be written (Requirement 5).

### Requirement 3: Curated pass list guarded by pytest

**User Story:** As a developer, I want the tests that are known to look right to be checked on every test run, so that a change that breaks SVG import is noticed immediately.

#### Acceptance Criteria

1. A checked-in **pass list** SHALL name the W3C tests that PressToShape handles correctly. A test goes on the list only after a developer has looked at it: matching by score alone is not enough (animation tests can match by accident, some reference images are outdated).
2. The initial pass list SHALL contain the in-scope tests from today's baseline that match and have been confirmed by eye.
3. An entry MAY carry a short comment, e.g. why a test is on the list despite an outdated reference image, or a per-test threshold when the default is too strict or too loose for it.
4. WHEN pytest runs and the suite is in the cache THEN every listed test SHALL be checked: it opens without error, survives save → reopen, and its difference score stays below its threshold. A failing entry SHALL fail the test run with the test name and score.
5. WHEN pytest runs and the suite is not in the cache THEN the conformance tests SHALL be skipped with a message naming the fetch command; the rest of the test suite SHALL be unaffected.
6. A pass-list entry naming a test that doesn't exist in the suite SHALL fail the test run (typos don't hide silently).

### Requirement 4: Generator check with an independent renderer

**User Story:** As a user exchanging files with other programs, I want SVG files saved by PressToShape to look the same elsewhere as in PressToShape, so that I can rely on what I hand over.

#### Acceptance Criteria

1. The project SHALL use **resvg** as the independent reference renderer, as a pinned development dependency available on Linux and Windows. The application SHALL NOT import it.
2. WHEN pytest runs THEN a set of documents built by the tests SHALL be saved as SVG, rendered by resvg and by PressToShape's PNG export, and the two renderings SHALL match within the difference threshold. The set SHALL cover every kind of object and style PressToShape can save today: rectangles (with and without rounded corners), ellipses, paths (open, closed, with holes in both fill rules), text with each anchor, groups with opacity, Composites, transforms (rotation, skew), opacities, caps, joins, miter limit, dashes, hidden objects and hidden layers.
3. WHEN pytest runs and the suite is in the cache THEN every pass-list test SHALL also go through the generator check: open, save as SVG, render the saved file with resvg, and compare with PressToShape's rendering of the same document.
4. Text MAY be compared with a looser threshold or masked out where both renderers pick different fonts for the same family; the reason SHALL be written next to the setting.
5. Every SVG file written in these checks SHALL be well-formed XML with the SVG namespace on the root element, and SHALL be accepted by resvg without errors.

### Requirement 5: Recorded baseline

**User Story:** As the maintainer, I want the current conformance numbers written down in the repository, so that each level's progress is visible in the history.

#### Acceptance Criteria

1. WHEN the developer runs the report command with a "write summary" option THEN the script SHALL write a short committed document (in `docs/`) with the suite version, the date, the threshold, and the per-chapter in-scope numbers (tests / matches / on the pass list).
2. The summary document SHALL explain in a few lines how to fetch the suite, run the report and add tests to the pass list.
3. The summary SHALL be deterministic for the same code and suite (sorted, no timestamps other than the date given), so rerunning without changes produces no diff.

## Non-Functional Requirements

### Code Architecture and Modularity
- The comparison and report logic SHALL be Qt-free and live outside the `presstoshape` package (developer tooling), reusing the public reader/writer (`formats/svg.py`) and PNG export (`render/export.py`) without changing them.
- Shared logic between the script and the pytest checks (loading the suite, rendering, scoring) SHALL exist once.
- The pass list SHALL be a plain text file that is easy to edit and diff.

### Performance
- The pytest conformance checks (pass list + generator check) SHALL add no more than about one minute to `uv run pytest` on a development machine; the full report may take a few minutes.

### Security
- The downloaded archive is untrusted until its checksum matches; extraction follows Requirement 1.4. Rendering untrusted test files uses the same reader as the app, which already must not execute content or fetch external resources.
- resvg SHALL be configured not to load external resources other than files inside the suite folder.

### Reliability
- Results SHALL be deterministic for the same code, suite and fonts. Font-dependent differences are handled by thresholds or masks (Requirement 4.4), not by retrying.
- Missing optional pieces (suite not fetched) skip with a clear message, never fail confusingly.

### Usability
- One documented command each for: fetch, report (optionally for a name pattern), write summary.
- The report is readable without opening code: a Markdown or HTML page with the per-chapter table, per-test rows and links to the side-by-side images.
