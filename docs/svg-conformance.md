# SVG conformance

How PressToShape opens the static part of the W3C SVG 1.1 (Second Edition) test suite: each test
is opened, saved and reopened, and rendered next to the suite's reference image. A test counts as
a match when under 3% of its pixels differ noticeably. That is a rough automatic
check, so a test only joins the pass list after someone has compared it by eye.

Suite: `https://www.w3.org/Graphics/SVG/Test/20110816/archives/W3C_SVG_11_TestSuite.tar.gz` (SHA-256 `b5f46cca1ad79b670f9179770b2366c57efd5c671d084144090feab4b7ff1030`).

- Fetch the suite once: `uv run python scripts/svg_conformance.py fetch`
- Report: `uv run python scripts/svg_conformance.py report [--filter 'struct-*']`, then open
  `build/svg-conformance/index.html` (side-by-side images of every in-scope test that doesn't match).
- Pass list: `tests/scripts/svg_conformance_pass.txt`, checked by `uv run pytest` while the suite is
  fetched. Add tests after checking them by eye; the report lists matching candidates. Tests that were
  looked at and aren't right yet are kept there as `!name # reason`.
- This page: `uv run python scripts/svg_conformance.py report --write-summary`.

## Status 2026-10-23

| Chapter | Tests | Match | On pass list |
|---|---|---|---|
| color | 5 | 3 | 3 |
| conform | 2 | 1 | 0 |
| coords | 28 | 26 | 25 |
| filters | 43 | 2 | 0 |
| imp | 1 | 0 | 0 |
| linking | 12 | 9 | 9 |
| masking | 19 | 15 | 13 |
| metadata | 1 | 1 | 1 |
| painting | 31 | 28 | 21 |
| paths | 19 | 18 | 18 |
| pservers | 33 | 22 | 21 |
| render | 8 | 3 | 3 |
| shapes | 22 | 22 | 22 |
| struct | 54 | 34 | 27 |
| styling | 18 | 12 | 11 |
| text | 54 | 30 | 8 |
| types | 2 | 1 | 1 |
| **Total** | **352** | **227** | **183** |

Out of scope (animation, scripting, DOM, interactivity, SVG fonts, colour profiles): animate (78), color-prof (1), coords-dom (4), extend (1), fonts (17), interact (24), paths-dom (2), script (6), struct-dom (18), svgdom (1), text-altglyph (3), text-dom (5), types-dom (13).
