# Requirements Document

## Introduction

Level 1 of the SVG conformance roadmap (feature gap list, "SVG conformance"): make what PressToShape already reads correct, without new kinds of object. Level 0 measured it against the W3C SVG 1.1 suite (`docs/svg-conformance.md`: 116 of 352 in-scope tests on the pass list). Looking through the failing tests and the reader's code showed these gaps in the basics:

- **One broken value can stop a whole file from opening.** A single malformed path (`paths-data-20-f`) makes the reader raise, so the user gets an error instead of a drawing. Other invalid values are guessed at instead of being ignored (`stroke-width="10PX"` is read as 10, `types-basic-02-f`).
- **Lengths with units** relative to the font or the viewport (`%`, `em`, `ex`) come out wrong (`coords-units-02-b`).
- **`color` and `currentColor`** are ignored; such shapes turn black (`painting-fill-02-t`, `struct-group-03-t`, `color-prop-*`).
- **CSS** only knows type, class and id selectors. Descendant, child, sibling and attribute selectors are skipped, and `<style>` elements with a foreign `type` are applied anyway (`styling-css-*`, `styling-elem-01-b`).
- **Conditional processing** is missing: `<switch>` shows all its alternatives, and `systemLanguage` / `requiredExtensions` on any element are ignored (`struct-cond-*`).
- **Text whitespace** follows neither SVG's default rules nor `xml:space="preserve"`, and saved text with double spaces loses them in other programs (`text-ws-*`).
- **Strokes under uneven scaling** (`scale(8,2)`, skew) silently get an average width; skewed text silently loses its skew (`paths-data-18-f`).

Two small tooling additions keep the measurement honest: tests whose W3C reference image is older than the test can be checked against resvg instead, and the baseline is updated.

Decisions taken before writing (2026-10-21):

- Uneven stroke scaling: keep today's approximation and **report it**; exact support comes later (path transforms or variable-width strokes belong to the artist/brush work).
- `currentColor`: **SVG 2 / CSS Color 4** behaviour, as browsers and resvg do (the keyword is inherited and resolved per element). The SVG 1.1 test `color-prop-05-t` expects the 1.1 rule and stays a reviewed exception.
- Conditional processing: **browser rules**, languages matched against the **app's UI language, then English**; `requiredFeatures` ignored as in SVG 2.

Out of scope here: nested `<svg>`, `preserveAspectRatio` and root sizes in `%` (Level 2), gradients and patterns (3), clipping and masks (4), images and references into other files (5), markers (6), per-tspan styles, fonts and text layout (7), filters (8).

## Alignment with Product Vision

- **Success metric, Interop**: "common Inkscape and Illustrator-exported SVG files open correctly". A file that refuses to open over one bad path is the worst interop failure; CSS combinators and `currentColor` are common in icon sets and web exports.
- **Principle 4**: "features SVG can't express degrade predictably … instead of silently disappearing". The same in the other direction: every approximation the reader makes (uneven strokes, skewed text, left-out alternatives, ignored values) gets an import note.
- **Principle 5, Inkscape interop**: whitespace in saved text survives other programs.
- **Tech steering, Security**: files are untrusted input and must not crash the reader; Level 1 removes the known crash.

## Requirements

### Requirement 1: Invalid values never block a file

**User Story:** As a user opening an SVG from an unknown source, I want the drawing to open even when parts of it are malformed, so that I can still work with everything that is valid.

#### Acceptance Criteria

1. WHEN a path's `d` contains an error THEN the reader SHALL keep the path up to the last complete segment before the error, as the SVG specification's path error handling says, and SHALL NOT fail the file. A path with no complete segment is left out.
2. The same SHALL hold for `points` on `<polyline>` and `<polygon>`: points up to the error are kept; an odd number of coordinates drops the last one.
3. WHEN a presentation attribute or CSS property has a value that isn't valid for it THEN the reader SHALL ignore that declaration, as if it were absent (the inherited or default value applies), instead of guessing. This includes units in the wrong case in presentation attributes (`stroke-width="10PX"`), while CSS units stay case-insensitive (`stroke-width: 20PX` in a style sheet or `style` attribute is valid).
4. WHEN a transform list is invalid THEN it SHALL be ignored as a whole (identity), as today.
5. WHEN anything in requirements 1.1–1.3 happens THEN the import report SHALL say how many paths were cut short and how many values were ignored.
6. Opening SHALL still fail with a message only for files that aren't usable at all (not XML, no `<svg>` root), as today.
7. Tests: `paths-data-20-f`, `types-basic-02-f` become passing.

### Requirement 2: Lengths and units

**User Story:** As a designer opening files from other tools, I want sizes in any SVG unit to come out right, so that drawings keep their proportions.

#### Acceptance Criteria

1. Lengths SHALL accept the SVG/CSS units `px`, `pt`, `pc`, `mm`, `cm`, `in`, `em`, `ex` and `%`, with the same conversions as today for absolute units.
2. `em` SHALL be relative to the element's font size; `ex` to half of it (the usual fallback when no x-height is known). For `font-size` itself they SHALL be relative to the parent's font size.
3. `%` SHALL be relative to the root viewport (the document's viewBox, or its width and height when there is none): horizontal lengths (`x`, `cx`, `width`, `rx`, …) to its width, vertical ones (`y`, `cy`, `height`, `ry`, …) to its height, and other lengths (`r`, `stroke-width`, dash lengths) to the diagonal ÷ √2, as SVG defines. `font-size` in `%` is relative to the parent's font size.
4. Tests: `coords-units-02-b` becomes passing; `coords-units-01-b` and `-03-b` are checked by eye (01 also needs gradients).

### Requirement 3: `color` and `currentColor`

**User Story:** As a user opening icon sets and web graphics, I want shapes painted with `currentColor` to keep their colour, so that they don't turn black.

#### Acceptance Criteria

1. The `color` property SHALL be read (attribute, CSS, inline style) and inherited.
2. `currentColor` in `fill` and `stroke` SHALL resolve to the `color` value of the element that is painted. The keyword itself is inherited, so a child with its own `color` uses its own (SVG 2 / CSS Color 4, as browsers and resvg do).
3. `color` itself MAY be `currentColor` or `inherit`, meaning the parent's colour. Without any `color`, `currentColor` is black.
4. Colour alpha in `color` (`rgba()`, `#rrggbbaa`, …) SHALL multiply into the paint opacity the same way as fill and stroke colours do today.
5. CSS2 system colours (`ActiveBorder`, `Window`, …) are deprecated and SHALL be treated as invalid values (Requirement 1.3).
6. Tests: `painting-fill-02-t`, `struct-group-03-t` become passing; `color-prop-05-t` becomes a reviewed exception with the reason "SVG 1.1 inherits the computed colour; we follow SVG 2 and browsers"; `color-prop-04-t` a reviewed exception for system colours.

### Requirement 4: CSS selectors and style sheets

**User Story:** As a user opening SVG exported from web tools and design apps, I want their style sheets applied as browsers apply them, so that colours and strokes come out right.

#### Acceptance Criteria

1. Selectors SHALL support, in addition to today's type, class, id and universal selectors and comma lists:
   - combinators: descendant (` `), child (`>`), adjacent sibling (`+`), general sibling (`~`);
   - attribute selectors: `[a]`, `[a=v]`, `[a~=v]`, `[a|=v]`, `[a^=v]`, `[a$=v]`, `[a*=v]`, with quoted or unquoted values;
   - structural pseudo-classes `:first-child`, `:last-child`, `:only-child`, `:nth-child(…)` (`odd`, `even`, `An+B`), `:not(simple selector)`, `:root`, `:lang(…)`;
   - `:link` for `<a>` elements with a link; `:visited`, `:hover`, `:active`, `:focus` never match (a static drawing has no visited links or pointer).
2. Specificity and order SHALL follow CSS: `!important` > inline `style` > sheet rules by specificity, then source order > presentation attributes > inherited values. Presentation attributes keep the lowest priority, as today.
3. Pseudo-elements (`::first-line`, `::first-letter`, `::before`, …) and other unsupported selectors SHALL skip only their rule and count it in the existing CSS note, as today.
4. `<style>` elements SHALL be used only when their `type` is absent, empty or `text/css` (case-insensitive) and their `media` is absent, empty, `all` or `screen`. `@media` blocks for `all` or `screen` SHALL be applied; other at-rules (`@import`, `@font-face`, `@media print`, …) are skipped and counted, as today.
5. CSS property values SHALL accept units case-insensitively (Requirement 1.3).
6. Matching SHALL stay fast on large files: a document with 10,000 shapes and a style sheet of 200 rules opens without noticeable delay compared to today.
7. Tests: `styling-css-02-b`, `-03-b`, `-04-f`, `-05-b`, `-06-b`, `-10-f`, `styling-elem-01-b`, `struct-use-10-f`, `struct-use-11-f`, `render-elems-06…08-t` are checked; those that also need Level 2 (nested `<svg>`) or fonts become reviewed exceptions with that reason.

### Requirement 5: Conditional processing

**User Story:** As a user opening multilingual or fallback-based SVG, I want the alternative a browser would show, so that I don't get all alternatives stacked on each other.

#### Acceptance Criteria

1. An element with `systemLanguage` SHALL be drawn only if one of the user's languages matches one of the listed language tags, exactly or as a prefix followed by `-` (`en` matches `en-US`). The user's languages are the app's UI language, then English.
2. An element with `requiredExtensions` SHALL NOT be drawn (PressToShape supports no extensions); an empty value also evaluates to false.
3. `requiredFeatures` SHALL be ignored (always true), as in SVG 2 and browsers.
4. A `<switch>` SHALL draw only its first direct child that is a drawable element and whose conditions are true; the other children are left out.
5. Conditions SHALL apply to every element, including groups, `<use>` and elements referenced by `<use>`.
6. WHEN alternatives or conditional elements are left out THEN the import report SHALL say how many. Saving writes only what was kept.
7. The reader SHALL take the user's languages as a plain parameter (no Qt or settings access in `formats/`); the app passes its UI language.
8. Tests: `struct-cond-01-t`, `-02-t`, `-03-t`, `struct-cond-overview-02…05-f` are checked by eye against the requirement (several references show failing renderers); those that pass join the pass list.

### Requirement 6: Text whitespace

**User Story:** As a user exchanging text with other programs, I want spaces in text to come out as the author meant, so that words neither run together nor drift apart.

#### Acceptance Criteria

1. With `xml:space="default"` (or none) the reader SHALL remove line breaks, turn tabs into spaces, collapse runs of spaces into one, and trim leading and trailing spaces of each text object, as SVG 1.1 defines.
2. With `xml:space="preserve"` the reader SHALL turn line breaks and tabs into spaces and keep every space, including leading and trailing ones.
3. `xml:space` SHALL be inherited by `<tspan>` and other children and MAY change on each of them; spaces at the boundary between a text element and its children SHALL be handled as one continuous string, so no space is lost or doubled at the boundary.
4. WHEN text with a leading, trailing or repeated space is saved as SVG THEN the writer SHALL write `xml:space="preserve"` on that `<text>`, so other programs keep the spaces. Text without such spaces is written as today.
5. Text SHALL survive save → reopen unchanged, including its spaces.
6. Tests: `text-ws-01-t`, `-02-t`, `-03-t` become passing (01 and 02 checked against resvg, Requirement 8).

### Requirement 7: Reported approximations of transforms

**User Story:** As a user, I want to know when a shape could only be approximated, so that I can check it instead of trusting a silently changed drawing.

#### Acceptance Criteria

1. WHEN a stroked shape is read under a transform that scales unevenly or skews (so its stroke width would differ by direction) THEN the reader SHALL keep today's approximation (stroke width and dashes scaled by the square root of the area scale) and the import report SHALL say how many strokes were approximated.
2. WHEN text is read under a skewing transform THEN the reader SHALL keep today's behaviour (skew dropped) and the import report SHALL say how many texts lost their skew.
3. Tests: `paths-data-18-f` becomes a reviewed exception with the reason "stroke under scale(8,2) approximated (uneven stroke)".

### Requirement 8: Measuring against resvg where the reference is outdated

**User Story:** As a developer, I want tests with an outdated W3C reference image to still guard the code, so that correct results don't sit outside the pass list forever.

#### Acceptance Criteria

1. The pass list SHALL accept `~name # reason` for a test whose W3C reference image is older than the test or otherwise wrong; such a test is compared with resvg's rendering of the original file instead of the reference image, with the usual threshold, and is checked by pytest like any other entry.
2. The report SHALL show these entries with their reason and use resvg's rendering for their score.
3. Tests already known: `styling-pres-03-f` (reference blank, green rect expected by the test), `text-ws-01-t` (reference without the current draft banner).

### Requirement 9: Updated baseline

**User Story:** As the maintainer, I want the conformance numbers updated with this level, so that its progress is recorded.

#### Acceptance Criteria

1. Every test this level makes correct SHALL be on the pass list after a check by eye; reviewed exceptions it fixes SHALL be turned into normal entries.
2. `docs/svg-conformance.md` SHALL be regenerated, and the feature gap list's Level 1 ticked.
3. No test on the pass list before this level SHALL leave it.

## Non-Functional Requirements

### Code Architecture and Modularity
- All changes stay in `formats/` (reader, writer, `css.py`, `svg_values.py`, `svg_notes.py`) plus the language parameter passed in from `editing/` or `views/`, and the conformance script for Requirement 8. No Qt below `views/`.
- Selector matching is its own unit in `css.py`, testable without the reader.
- New import notes follow the existing `Note` / `NoteCollector` pattern and are translated (`de.po`).

### Performance
- Opening a 10,000-shape SVG with CSS stays within 10 % of today's time.
- The conformance pytest run stays within about a minute.

### Security
- Malformed input never raises out of the reader for the cases above; selector parsing is bounded (no catastrophic regex backtracking on hostile style sheets).

### Reliability
- Every SVG that opens today still opens, and the pass list from Level 0 stays green.
- Round trips (`.p2s` and SVG) stay lossless for everything the model holds.

### Usability
- Import notes are short, counted, and say what happened ("3 paths had errors and were cut short", "2 strokes under uneven scaling were approximated").
