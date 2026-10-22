"""Dev-only: measures PressToShape against the W3C SVG 1.1 (Second Edition) test suite.

Usage: uv run python scripts/svg_conformance.py <command> [options]
  fetch                                   download the pinned suite into build/svg-suites/w3c-svg11 (once)
  report [--filter GLOB] [--write-summary [--date YYYY-MM-DD]]
                                          check every test, write build/svg-conformance/index.html;
                                          --write-summary also updates docs/svg-conformance.md

The app never imports this script; tests/scripts/test_svg_conformance.py and tests/formats/test_svg_generator.py
load it for the shared checks.
"""

import argparse
import datetime
import hashlib
import html
import io
import shutil
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Literal

import numpy as np
import resvg_py
import skia

ROOT = Path(__file__).resolve().parent.parent

SUITE = (
    "https://www.w3.org/Graphics/SVG/Test/20110816/archives/W3C_SVG_11_TestSuite.tar.gz",
    "b5f46cca1ad79b670f9179770b2366c57efd5c671d084144090feab4b7ff1030",
)
CACHE = ROOT / "build" / "svg-suites" / "w3c-svg11"
FETCH_HINT = "run: uv run python scripts/svg_conformance.py fetch"
_MARKER = ".complete"
PASS_LIST = ROOT / "tests" / "scripts" / "svg_conformance_pass.txt"
REPORT = ROOT / "build" / "svg-conformance"
SUMMARY = ROOT / "docs" / "svg-conformance.md"

sys.path.insert(0, str(ROOT))
from presstoshape.formats.svg import read_svg, read_svg_with_notes, write_svg  # noqa: E402
from presstoshape.formats.svg_names import q  # noqa: E402
from presstoshape.models.app_state import Document  # noqa: E402
from presstoshape.render.export import export_size, render_png  # noqa: E402
from presstoshape.render.text import typeface  # noqa: E402

# --- Suite and cache --------------------------------------------------------------------------


def suite_folder(cache: Path = CACHE) -> Path | None:
    """The extracted suite, or None when it isn't there or comes from another archive."""
    marker = cache / _MARKER
    if marker.is_file() and marker.read_text().strip() == SUITE[1]:
        return cache
    return None


def fetch(cache: Path = CACHE) -> bool:
    """Download, verify and extract the suite; False when the cache was already complete."""
    if suite_folder(cache) is not None:
        return False
    url, expected = SUITE
    with urllib.request.urlopen(url, timeout=120) as response:
        data = response.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise SystemExit(f"checksum mismatch for {url}: expected {expected}, got {actual}")
    extract(data, cache)
    return True


def extract(archive: bytes, cache: Path) -> None:
    """Unpack into a sibling folder first, so an interrupted or refused extraction never looks complete."""
    partial = cache.with_name(cache.name + ".partial")
    shutil.rmtree(partial, ignore_errors=True)
    partial.mkdir(parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
            # The "data" filter refuses members and links that would land outside the folder.
            tar.extractall(partial, filter="data")
    except BaseException:
        shutil.rmtree(partial, ignore_errors=True)
        raise
    (partial / _MARKER).write_text(SUITE[1] + "\n")
    shutil.rmtree(cache, ignore_errors=True)
    partial.rename(cache)


# --- Pass list and scope ---------------------------------------------------------------------

# Non-goals (FEATURE_GAPS.md): an editor works on static drawings, so animation, scripting, DOM, interactivity,
# SVG fonts, colour profiles and extensibility tests say nothing about us.
_OUT_OF_SCOPE_CHAPTERS = frozenset({"animate", "script", "interact", "svgdom", "fonts", "extend"})
_OUT_OF_SCOPE_SUBCHAPTERS = frozenset({"color-prof", "text-altglyph"})


def chapter(name: str) -> str:
    return name.split("-")[0]


def subchapter(name: str) -> str:
    return "-".join(name.split("-")[:2])


def in_scope(name: str) -> bool:
    parts = name.split("-")
    return (
        parts[0] not in _OUT_OF_SCOPE_CHAPTERS
        and subchapter(name) not in _OUT_OF_SCOPE_SUBCHAPTERS
        and (len(parts) < 2 or parts[1] != "dom")
    )


@dataclass(frozen=True)
class PassEntry:
    name: str
    threshold: float
    comment: str = ""
    # False for `!name # reason`: looked at, matches by score but isn't right yet. Keeps it out of the candidates.
    passes: bool = True
    # "resvg" for `~name # reason`: the suite's own reference image is outdated, so the test is scored against
    # resvg's rendering of the original file instead.
    reference: Literal["w3c", "resvg"] = "w3c"


def read_pass_list(path: Path = PASS_LIST) -> dict[str, PassEntry]:
    """Lines `name [threshold] [# comment]`, `!name # reason` or `~name [threshold] # reason`; blank and
    comment-only lines are skipped."""
    entries: dict[str, PassEntry] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        content, _hash, comment = line.partition("#")
        fields = content.split()
        if not fields:
            continue
        if len(fields) > 2:
            raise ValueError(f"{path.name}:{number}: expected 'name [threshold] [# comment]'")
        name = fields[0].removeprefix("!").removeprefix("~")
        passes = not fields[0].startswith("!")
        reference: Literal["w3c", "resvg"] = "resvg" if fields[0].startswith("~") else "w3c"
        if not passes and (len(fields) > 1 or not comment.strip()):
            raise ValueError(f"{path.name}:{number}: expected '!name # reason'")
        if reference == "resvg" and not comment.strip():
            raise ValueError(f"{path.name}:{number}: expected '~name [threshold] # reason'")
        threshold = THRESHOLD
        if len(fields) == 2:
            try:
                threshold = float(fields[1])
            except ValueError:
                raise ValueError(f"{path.name}:{number}: threshold {fields[1]!r} is not a number") from None
            if not 0 < threshold <= 1:
                raise ValueError(f"{path.name}:{number}: threshold must be in (0, 1]")
        if name in entries:
            raise ValueError(f"{path.name}:{number}: {name} is listed twice")
        entries[name] = PassEntry(name, threshold, comment.strip(), passes, reference)
    return entries


def passing(pass_list: Mapping[str, PassEntry]) -> dict[str, PassEntry]:
    return {name: entry for name, entry in pass_list.items() if entry.passes}


# --- Rendering and scoring --------------------------------------------------------------------

THRESHOLD = 0.03
# The blur hides anti-aliasing and small glyph-shape differences; a missing or recoloured shape still counts.
BLUR_SIGMA = 3
CHANNEL_TOLERANCE = 60
# What PressToShape writes as font-family="sans-serif" must reach resvg as the same font Skia draws with.
SANS = typeface().getFamilyName()


def decoded(png: bytes) -> skia.Image:
    # MakeFromEncoded decodes lazily from the bytes' buffer, which may be freed by the time the image is drawn.
    return skia.Image.MakeFromEncoded(png).makeRasterImage()


def pixels(png: bytes) -> np.ndarray:
    """RGB (height, width, 3) of `png` composited on white and blurred."""
    image = decoded(png)
    surface = skia.Surface(image.width(), image.height())
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorWHITE)
    blur = skia.Paint(ImageFilter=skia.ImageFilters.Blur(BLUR_SIGMA, BLUR_SIGMA))
    canvas.drawImage(image, 0, 0, skia.SamplingOptions(), blur)
    return surface.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3].astype(np.int16)


def score(ours: np.ndarray, theirs: np.ndarray) -> float:
    """Share of pixels that differ noticeably; 1.0 when the sizes differ."""
    if ours.shape != theirs.shape:
        return 1.0
    return float((np.abs(ours - theirs).max(axis=2) > CHANNEL_TOLERANCE).mean())


def render_ours(doc: Document, width: int) -> bytes:
    png = render_png(doc, width / doc.width)
    if png is None:
        raise ValueError(f"document of {doc.width} x {doc.height} can't be rendered at width {width}")
    return png


def render_resvg(svg_text: str, width: int, height: int, resources_dir: Path | None = None) -> bytes:
    return resvg_py.svg_to_bytes(
        svg_string=svg_text,
        width=width,
        height=height,
        resources_dir=str(resources_dir) if resources_dir else None,
        sans_serif_family=SANS,
        languages=["en"],
    )


# --- Checks ----------------------------------------------------------------------------------

Status = Literal["match", "differs", "error"]


@dataclass(frozen=True)
class CheckResult:
    name: str
    in_scope: bool
    status: Status
    score: float | None
    notes: tuple[str, ...] = ()
    error: str | None = None


def check_test(
    suite: Path, name: str, threshold: float = THRESHOLD, reference: Literal["w3c", "resvg"] = "w3c"
) -> tuple[CheckResult, Document | None]:
    """Open a suite test with notes, save and reopen it, and score our rendering against the reference image
    (or, for reference "resvg", against resvg's rendering of the original file at the image's size)."""
    scope = in_scope(name)
    reference_png = suite / "png" / f"{name}.png"
    reference_source = reference
    if not reference_png.is_file():
        return CheckResult(name, scope, "error", None, error="no reference image"), None
    # Test files are foreign input: a reader or writer failure is a result to report, not a crash of the run.
    try:
        original = (suite / "svg" / f"{name}.svg").read_text(encoding="utf-8")
        doc, notes = read_svg_with_notes(original)
    except Exception as error:
        return CheckResult(name, scope, "error", None, error=f"{type(error).__name__}: {error}"), None
    try:
        read_svg(write_svg(doc))
    except Exception as error:
        message = f"round trip: {type(error).__name__}: {error}"
        return CheckResult(name, scope, "error", None, tuple(notes), message), doc
    theirs = pixels(reference_png.read_bytes())
    if reference_source == "resvg":
        theirs = pixels(render_resvg(original, theirs.shape[1], theirs.shape[0], suite / "svg"))
    value = score(pixels(render_ours(doc, theirs.shape[1])), theirs)
    status: Status = "match" if value < threshold else "differs"
    return CheckResult(name, scope, status, value, tuple(notes)), doc


def suite_tests(suite: Path, pattern: str | None = None) -> list[str]:
    names = sorted(path.stem for path in (suite / "svg").glob("*.svg"))
    return [name for name in names if pattern is None or fnmatch(name, pattern)]


def check_suite(
    suite: Path,
    pattern: str | None = None,
    thresholds: Mapping[str, float] = {},
    references: Mapping[str, Literal["w3c", "resvg"]] = {},
) -> list[CheckResult]:
    return [
        check_test(suite, name, thresholds.get(name, THRESHOLD), references.get(name, "w3c"))[0]
        for name in suite_tests(suite, pattern)
    ]


def check_generator(doc: Document) -> float:
    """Score of resvg's rendering of the saved SVG against ours; raises when the file isn't SVG resvg accepts."""
    text = write_svg(doc)
    root = ET.fromstring(text)
    if root.tag != q("svg"):
        raise ValueError(f"root element is {root.tag}, not an SVG <svg>")
    width, height = export_size(doc, 1.0)
    return score(pixels(render_ours(doc, width)), pixels(render_resvg(text, width, height)))


# --- Report and summary ----------------------------------------------------------------------

_SHEET_GAP = 8


def sheet(suite: Path, name: str) -> bytes:
    """PressToShape | W3C reference | resvg of the original file, side by side; a panel stays empty when its
    renderer can't handle the file."""
    reference = decoded((suite / "png" / f"{name}.png").read_bytes())
    width, height = reference.width(), reference.height()
    svg_text = (suite / "svg" / f"{name}.svg").read_text(encoding="utf-8")
    panels: list[skia.Image | None] = [None, reference, None]
    # Foreign input again: the report shows what each renderer makes of it, failures included.
    try:
        panels[0] = decoded(render_ours(read_svg(svg_text), width))
    except Exception:
        pass
    try:
        panels[2] = decoded(render_resvg(svg_text, width, height, suite / "svg"))
    except Exception:
        pass
    surface = skia.Surface(3 * width + 2 * _SHEET_GAP, height)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorSetRGB(0x88, 0x88, 0x88))
    for index, panel in enumerate(panels):
        left = index * (width + _SHEET_GAP)
        canvas.drawRect(skia.Rect.MakeXYWH(left, 0, width, height), skia.Paint(Color=skia.ColorWHITE))
        if panel is not None:
            canvas.drawImage(panel, left, 0)
    return bytes(surface.makeImageSnapshot().encodeToData())


@dataclass
class _Tally:
    tests: int = 0
    match: int = 0
    differs: int = 0
    error: int = 0
    listed: int = 0

    def add(self, result: CheckResult, listed: bool) -> None:
        self.tests += 1
        setattr(self, result.status, getattr(self, result.status) + 1)
        self.listed += listed


def _tallies(results: Sequence[CheckResult], pass_list: Mapping[str, PassEntry], key) -> dict[str, _Tally]:
    tallies: dict[str, _Tally] = defaultdict(_Tally)
    for result in results:
        if result.in_scope:
            tallies[key(result.name)].add(result, result.name in pass_list and pass_list[result.name].passes)
    return dict(sorted(tallies.items()))


def _total(tallies: Mapping[str, _Tally]) -> _Tally:
    total = _Tally()
    for tally in tallies.values():
        for field in ("tests", "match", "differs", "error", "listed"):
            setattr(total, field, getattr(total, field) + getattr(tally, field))
    return total


def candidates(results: Sequence[CheckResult], pass_list: Mapping[str, PassEntry]) -> tuple[list[str], list[str]]:
    """(in-scope matches not on the pass list at all, passing entries that were checked and no longer match)."""
    new = [
        result.name
        for result in results
        if result.in_scope and result.status == "match" and result.name not in pass_list
    ]
    lost = [result.name for result in results if result.name in passing(pass_list) and result.status != "match"]
    return new, lost


def _scope_group(name: str) -> str:
    """The rule that puts an out-of-scope test out of scope: its chapter, sub-chapter or `<chapter>-dom`."""
    if chapter(name) in _OUT_OF_SCOPE_CHAPTERS:
        return chapter(name)
    if subchapter(name) in _OUT_OF_SCOPE_SUBCHAPTERS:
        return subchapter(name)
    return f"{chapter(name)}-dom"


def _out_of_scope(results: Sequence[CheckResult]) -> Counter[str]:
    return Counter(sorted(_scope_group(result.name) for result in results if not result.in_scope))


_STYLE = """
:root { color-scheme: light dark; --bg: #ffffff; --fg: #1c1c1e; --muted: #6b6b70; --line: #d8d8dc;
  --match: #1f7a3a; --differs: #a15c00; --error: #b3261e; }
@media (prefers-color-scheme: dark) { :root { --bg: #18181a; --fg: #ececee; --muted: #a0a0a6; --line: #3a3a3e;
  --match: #5fcf7f; --differs: #f0a542; --error: #ff7b72; } }
body { background: var(--bg); color: var(--fg); font: 14px/1.45 system-ui, sans-serif; margin: 24px auto;
  max-width: 1200px; padding: 0 16px; }
table { border-collapse: collapse; margin: 8px 0 24px; }
th, td { border-bottom: 1px solid var(--line); padding: 4px 10px; text-align: left; vertical-align: top; }
td.number, th.number { text-align: right; font-variant-numeric: tabular-nums; }
.match { color: var(--match); } .differs { color: var(--differs); } .error { color: var(--error); }
.muted { color: var(--muted); }
"""


def _tally_table(title: str, tallies: Mapping[str, _Tally]) -> str:
    head = "".join(f'<th class="number">{label}</th>' for label in ("Tests", "Match", "Differs", "Error", "Listed"))
    rows = []
    for label, tally in [*tallies.items(), ("Total", _total(tallies))]:
        cells = "".join(
            f'<td class="number">{value}</td>'
            for value in (tally.tests, tally.match, tally.differs, tally.error, tally.listed)
        )
        rows.append(f"<tr><td>{html.escape(label)}</td>{cells}</tr>")
    return f"<h2>{title}</h2><table><tr><th></th>{head}</tr>{''.join(rows)}</table>"


def write_report(
    results: Sequence[CheckResult], suite: Path, pass_list: Mapping[str, PassEntry], folder: Path = REPORT
) -> Path:
    shutil.rmtree(folder, ignore_errors=True)
    (folder / "sheets").mkdir(parents=True)
    new, lost = candidates(results, pass_list)
    out_of_scope = _out_of_scope(results)
    parts = [
        f"<!doctype html><html lang=en><head><meta charset=utf-8><title>SVG conformance</title><style>{_STYLE}</style>",
        "</head><body><h1>SVG conformance: W3C SVG 1.1 Second Edition</h1>",
        f'<p class="muted">Match: under {THRESHOLD:.0%} of pixels differ noticeably (or the pass-list threshold). '
        "Sheets: PressToShape | W3C reference | resvg.</p>",
        _tally_table("In scope, per chapter", _tallies(results, pass_list, chapter)),
        _tally_table("In scope, per sub-chapter", _tallies(results, pass_list, subchapter)),
        "<h2>Out of scope</h2><p>"
        + (", ".join(f"{html.escape(name)} ({count})" for name, count in out_of_scope.items()) or "none")
        + "</p>",
        f"<h2>Candidates</h2><p>Matching, not on the pass list ({len(new)}): "
        + (", ".join(f'<a href="#{name}">{name}</a>' for name in new) or "none")
        + f"</p><p>On the pass list, no longer matching ({len(lost)}): "
        + (", ".join(f'<a href="#{name}" class="error">{name}</a>' for name in lost) or "none")
        + "</p>",
        "<h2>Tests</h2><table><tr><th>Test</th><th>Status</th><th class=number>Score</th><th>Notes</th><th></th></tr>",
    ]
    for result in sorted(results, key=lambda result: (not result.in_scope, result.name)):
        link = ""
        if result.in_scope and result.status != "match" and (suite / "png" / f"{result.name}.png").is_file():
            (folder / "sheets" / f"{result.name}.png").write_bytes(sheet(suite, result.name))
            link = f'<a href="sheets/{result.name}.png">sheet</a>'
        score_text = "" if result.score is None else f"{result.score:.2%}"
        details = [html.escape(note) for note in result.notes]
        if result.error:
            details.append(f'<span class="error">{html.escape(result.error)}</span>')
        name = html.escape(result.name) + ("" if result.in_scope else ' <span class="muted">(out of scope)</span>')
        entry = pass_list.get(result.name)
        listed = " ✓" if entry is not None and entry.passes else ""
        if entry is not None and entry.passes and entry.reference == "resvg":
            details.insert(0, f'<span class="muted">checked against resvg: {html.escape(entry.comment)}</span>')
        if entry is not None and not entry.passes:
            details.insert(0, f'<span class="muted">reviewed, not yet right: {html.escape(entry.comment)}</span>')
        parts.append(
            f'<tr id="{html.escape(result.name)}"><td>{name}{listed}</td>'
            f'<td class="{result.status}">{result.status}</td><td class="number">{score_text}</td>'
            f"<td>{'<br>'.join(details)}</td><td>{link}</td></tr>"
        )
    parts.append("</table></body></html>\n")
    index = folder / "index.html"
    index.write_text("".join(parts), encoding="utf-8")
    return index


def summary(results: Sequence[CheckResult], pass_list: Mapping[str, PassEntry], date: str) -> str:
    tallies = _tallies(results, pass_list, chapter)
    rows = [f"| {name} | {t.tests} | {t.match} | {t.listed} |" for name, t in tallies.items()]
    total = _total(tallies)
    out_of_scope = ", ".join(f"{name} ({count})" for name, count in _out_of_scope(results).items())
    return "\n".join(
        [
            "# SVG conformance",
            "",
            "How PressToShape opens the static part of the W3C SVG 1.1 (Second Edition) test suite: each test",
            "is opened, saved and reopened, and rendered next to the suite's reference image. A test counts as",
            f"a match when under {THRESHOLD:.0%} of its pixels differ noticeably. That is a rough automatic",
            "check, so a test only joins the pass list after someone has compared it by eye.",
            "",
            f"Suite: `{SUITE[0]}` (SHA-256 `{SUITE[1]}`).",
            "",
            "- Fetch the suite once: `uv run python scripts/svg_conformance.py fetch`",
            "- Report: `uv run python scripts/svg_conformance.py report [--filter 'struct-*']`, then open",
            "  `build/svg-conformance/index.html` (side-by-side images of every in-scope test that doesn't match).",
            "- Pass list: `tests/scripts/svg_conformance_pass.txt`, checked by `uv run pytest` while the suite is",
            "  fetched. Add tests after checking them by eye; the report lists matching candidates. Tests that were",
            "  looked at and aren't right yet are kept there as `!name # reason`.",
            "- This page: `uv run python scripts/svg_conformance.py report --write-summary`.",
            "",
            f"## Status {date}",
            "",
            "| Chapter | Tests | Match | On pass list |",
            "|---|---|---|---|",
            *rows,
            f"| **Total** | **{total.tests}** | **{total.match}** | **{total.listed}** |",
            "",
            "Out of scope (animation, scripting, DOM, interactivity, SVG fonts, colour profiles): "
            f"{out_of_scope or 'none'}.",
            "",
        ]
    )


def write_summary(
    results: Sequence[CheckResult], pass_list: Mapping[str, PassEntry], date: str, path: Path = SUMMARY
) -> None:
    path.write_text(summary(results, pass_list, date), encoding="utf-8")


# --- CLI --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch", help="download the pinned W3C SVG 1.1 suite")
    report = commands.add_parser("report", help="check every test and write the HTML report")
    report.add_argument("--filter", help="only tests whose name matches this glob, e.g. 'struct-*'")
    report.add_argument("--write-summary", action="store_true", help=f"also write {SUMMARY.relative_to(ROOT)}")
    report.add_argument("--date", default=datetime.date.today().isoformat(), help="date for the summary")
    args = parser.parse_args(argv)
    if args.command == "fetch":
        if fetch():
            print(f"suite extracted to {CACHE}")
        else:
            print(f"suite already complete in {CACHE}")
        return 0
    suite = suite_folder()
    if suite is None:
        print(f"the W3C suite isn't fetched; {FETCH_HINT}", file=sys.stderr)
        return 1
    pass_list = read_pass_list() if PASS_LIST.is_file() else {}
    listed = passing(pass_list)
    results = check_suite(
        suite,
        args.filter,
        {name: entry.threshold for name, entry in listed.items()},
        {name: entry.reference for name, entry in listed.items()},
    )
    index = write_report(results, suite, pass_list)
    total = _total(_tallies(results, pass_list, chapter))
    new, lost = candidates(results, pass_list)
    print(f"in scope: {total.tests} tests, {total.match} match, {total.differs} differ, {total.error} errors")
    print(f"pass list: {total.listed} listed, {len(lost)} no longer matching; {len(new)} new candidates")
    if args.write_summary:
        if args.filter:
            print("--write-summary needs the whole suite; run without --filter", file=sys.stderr)
            return 1
        write_summary(results, pass_list, args.date)
        print(f"summary written to {SUMMARY}")
    print(f"report: {index}")
    return 1 if lost else 0


if __name__ == "__main__":
    sys.exit(main())
