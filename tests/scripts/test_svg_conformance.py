import hashlib
import importlib.util
import io
import re
import tarfile
from pathlib import Path

import pytest

from presstoshape.formats.svg import read_svg

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "svg_conformance.py"
_spec = importlib.util.spec_from_file_location("svg_conformance", _SCRIPT)
svg_conformance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(svg_conformance)


def _archive(*members: tarfile.TarInfo, content: bytes = b"<svg/>") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for member in members:
            if member.isfile():
                member.size = len(content)
                tar.addfile(member, io.BytesIO(content))
            else:
                tar.addfile(member)
    return buffer.getvalue()


def _file(name: str) -> tarfile.TarInfo:
    return tarfile.TarInfo(name)


def _symlink(name: str, target: str) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.type = tarfile.SYMTYPE
    member.linkname = target
    return member


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def serve(monkeypatch):
    """Serve `data` as the suite download, pinned to `pinned` (default: its own hash); returns a request counter."""
    requests = []

    def install(data: bytes, pinned: str | None = None):
        monkeypatch.setattr(svg_conformance, "SUITE", ("https://example.test/suite.tar.gz", pinned or _sha(data)))

        def urlopen(url, timeout):
            requests.append(url)
            return _Response(data)

        monkeypatch.setattr(svg_conformance.urllib.request, "urlopen", urlopen)
        return requests

    return install


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_fetch_extracts_the_suite_and_marks_it_complete(tmp_path, serve):
    serve(_archive(_file("svg/shapes-rect-01-t.svg")))
    cache = tmp_path / "w3c"
    assert svg_conformance.fetch(cache)
    assert (cache / "svg" / "shapes-rect-01-t.svg").read_bytes() == b"<svg/>"
    assert svg_conformance.suite_folder(cache) == cache


def test_second_fetch_does_nothing(tmp_path, serve):
    requests = serve(_archive(_file("svg/a.svg")))
    cache = tmp_path / "w3c"
    svg_conformance.fetch(cache)
    assert not svg_conformance.fetch(cache)
    assert len(requests) == 1


def test_wrong_checksum_writes_nothing_and_names_both_hashes(tmp_path, serve):
    data = _archive(_file("svg/a.svg"))
    serve(data, pinned="0" * 64)
    cache = tmp_path / "w3c"
    with pytest.raises(SystemExit) as error:
        svg_conformance.fetch(cache)
    assert "0" * 64 in str(error.value) and _sha(data) in str(error.value)
    assert not any(tmp_path.iterdir())


def test_cache_without_or_with_a_stale_marker_is_not_complete(tmp_path, serve):
    serve(_archive(_file("svg/a.svg")))
    cache = tmp_path / "w3c"
    (cache / "svg").mkdir(parents=True)
    assert svg_conformance.suite_folder(cache) is None
    (cache / ".complete").write_text("f" * 64)
    assert svg_conformance.suite_folder(cache) is None
    assert svg_conformance.fetch(cache)
    assert svg_conformance.suite_folder(cache) == cache


@pytest.mark.parametrize(
    "member", [_file("../evil.svg"), _symlink("svg/link", "../../outside"), _symlink("svg/abs", "/etc/passwd")]
)
def test_members_leaving_the_cache_are_refused(tmp_path, serve, member):
    serve(_archive(_file("svg/a.svg"), member))
    cache = tmp_path / "suites" / "w3c"
    with pytest.raises(tarfile.FilterError):
        svg_conformance.fetch(cache)
    assert not (tmp_path / "suites" / "evil.svg").exists()
    assert not (tmp_path / "evil.svg").exists()
    assert svg_conformance.suite_folder(cache) is None
    assert list((tmp_path / "suites").iterdir()) == []


def test_absolute_member_stays_inside_the_cache(tmp_path, serve):
    serve(_archive(_file("/abs.svg")))
    cache = tmp_path / "w3c"
    svg_conformance.fetch(cache)
    assert (cache / "abs.svg").is_file()


def _pass_list(tmp_path: Path, text: str) -> dict:
    path = tmp_path / "pass.txt"
    path.write_text(text, encoding="utf-8")
    return svg_conformance.read_pass_list(path)


def test_pass_list_reads_names_thresholds_and_comments(tmp_path):
    entries = _pass_list(
        tmp_path,
        "# header comment\n\nshapes-rect-01-t\npaths-data-01-t 0.05\nstyling-pres-03-f  # outdated reference\n"
        "text-ws-01-t 0.06 # glyphs\n!masking-path-12-f  # red instead of green, too small for the score\n",
    )
    assert entries == {
        "shapes-rect-01-t": svg_conformance.PassEntry("shapes-rect-01-t", svg_conformance.THRESHOLD),
        "paths-data-01-t": svg_conformance.PassEntry("paths-data-01-t", 0.05),
        "styling-pres-03-f": svg_conformance.PassEntry(
            "styling-pres-03-f", svg_conformance.THRESHOLD, "outdated reference"
        ),
        "text-ws-01-t": svg_conformance.PassEntry("text-ws-01-t", 0.06, "glyphs"),
        "masking-path-12-f": svg_conformance.PassEntry(
            "masking-path-12-f", svg_conformance.THRESHOLD, "red instead of green, too small for the score", False
        ),
    }


def test_resvg_reference_entries(tmp_path):
    entries = _pass_list(tmp_path, "~styling-pres-03-f # outdated reference\n~text-ws-01-t 0.06 # glyph shapes\n")
    assert entries == {
        "styling-pres-03-f": svg_conformance.PassEntry(
            "styling-pres-03-f", svg_conformance.THRESHOLD, "outdated reference", True, "resvg"
        ),
        "text-ws-01-t": svg_conformance.PassEntry("text-ws-01-t", 0.06, "glyph shapes", True, "resvg"),
    }


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("~a\n", "pass.txt:1: expected '~name [threshold] # reason'"),
        ("~a 0.05\n", "pass.txt:1: expected '~name [threshold] # reason'"),
        ("a\n~a # why\n", "pass.txt:2: a is listed twice"),
        ("~a # why\n!a # other\n", "pass.txt:2: a is listed twice"),
        ("a\nb c d\n", "pass.txt:2"),
        ("a 0.x\n", "not a number"),
        ("a 1.5\n", "(0, 1]"),
        ("a\n\na\n", "pass.txt:3: a is listed twice"),
        ("a\n!a # wrong colour\n", "pass.txt:2: a is listed twice"),
        ("!a\n", "pass.txt:1: expected '!name # reason'"),
        ("!a 0.05 # threshold\n", "pass.txt:1: expected '!name # reason'"),
    ],
)
def test_malformed_pass_list_names_the_line(tmp_path, text, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        _pass_list(tmp_path, text)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("shapes-rect-01-t", True),
        ("pservers-grad-01-b", True),
        ("text-ws-01-t", True),
        ("animate-elem-02-t", False),
        ("script-handle-01-b", False),
        ("interact-zoom-01-t", False),
        ("svgdom-over-01-f", False),
        ("fonts-elem-01-t", False),
        ("extend-namespace-01-f", False),
        ("color-prof-01-f", False),
        ("text-altglyph-01-b", False),
        ("struct-dom-01-b", False),
        ("types-dom-01-b", False),
    ],
)
def test_scope(name, expected):
    assert svg_conformance.in_scope(name) is expected


def test_chapter_and_subchapter():
    assert svg_conformance.chapter("pservers-grad-01-b") == "pservers"
    assert svg_conformance.subchapter("pservers-grad-01-b") == "pservers-grad"


_PICTURE = """<svg xmlns="http://www.w3.org/2000/svg" width="200" height="150" viewBox="0 0 200 150">
  <rect x="{x}" y="20" width="80" height="60" fill="#0050c8"/>
  {extra}
</svg>"""


def _rendered(x: float = 20, extra: str = '<circle cx="150" cy="100" r="40" fill="#e03020"/>'):
    return svg_conformance.pixels(svg_conformance.render_ours(read_svg(_PICTURE.format(x=x, extra=extra)), 200))


def test_identical_renders_score_zero():
    assert svg_conformance.score(_rendered(), _rendered()) == 0


def test_different_sizes_score_one():
    assert svg_conformance.score(_rendered(), _rendered()[:-1]) == 1.0


def test_a_missing_shape_counts_and_a_one_pixel_shift_does_not():
    assert svg_conformance.score(_rendered(), _rendered(extra="")) > svg_conformance.THRESHOLD
    assert svg_conformance.score(_rendered(), _rendered(x=21)) < svg_conformance.THRESHOLD


def test_resvg_and_presstoshape_agree_on_a_simple_picture():
    svg = _PICTURE.format(x=20, extra='<circle cx="150" cy="100" r="40" fill="#e03020"/>')
    theirs = svg_conformance.pixels(svg_conformance.render_resvg(svg, 200, 150))
    assert svg_conformance.score(_rendered(), theirs) < svg_conformance.THRESHOLD


def _result(name: str, status: str = "match", score: float | None = 0.01, **extra):
    return svg_conformance.CheckResult(name, svg_conformance.in_scope(name), status, score, **extra)


RESULTS = [
    _result("shapes-rect-01-t"),
    _result("shapes-rect-02-t", "differs", 0.2),
    _result("paths-data-20-f", "error", None, error="ValueError: bad path data"),
    _result("animate-elem-02-t"),
    _result("struct-dom-01-b", "differs", 0.5),
]
LISTED = {"shapes-rect-01-t": svg_conformance.PassEntry("shapes-rect-01-t", svg_conformance.THRESHOLD)}


def test_summary_is_deterministic_and_counts_in_scope_tests_only():
    text = svg_conformance.summary(RESULTS, LISTED, "2026-10-21")
    assert text == svg_conformance.summary(list(reversed(RESULTS)), LISTED, "2026-10-21")
    assert "## Status 2026-10-21" in text
    assert "| paths | 1 | 0 | 0 |" in text
    assert "| shapes | 2 | 1 | 1 |" in text
    assert "| **Total** | **3** | **1** | **1** |" in text
    assert "animate (1), struct-dom (1)" in text
    assert svg_conformance.SUITE[1] in text


def test_candidates_are_new_matches_and_lost_pass_list_entries():
    listed = LISTED | {
        "shapes-rect-02-t": svg_conformance.PassEntry("shapes-rect-02-t", svg_conformance.THRESHOLD),
        "paths-data-02-t": svg_conformance.PassEntry("paths-data-02-t", svg_conformance.THRESHOLD, "why", False),
        "paths-data-03-f": svg_conformance.PassEntry("paths-data-03-f", svg_conformance.THRESHOLD, "why", False),
    }
    results = [*RESULTS, _result("paths-data-01-t"), _result("paths-data-02-t"), _result("paths-data-03-f", "differs")]
    assert svg_conformance.candidates(results, listed) == (["paths-data-01-t"], ["shapes-rect-02-t"])


def test_reviewed_entries_do_not_count_as_listed():
    listed = LISTED | {"shapes-rect-02-t": svg_conformance.PassEntry("shapes-rect-02-t", 0.03, "why", False)}
    assert "| shapes | 2 | 1 | 1 |" in svg_conformance.summary(RESULTS, listed, "2026-10-21")


def _fake_suite(tmp_path: Path) -> Path:
    suite = tmp_path / "suite"
    (suite / "svg").mkdir(parents=True)
    (suite / "png").mkdir()
    picture = _PICTURE.format(x=20, extra="")
    for name in ("shapes-rect-01-t", "shapes-rect-02-t", "animate-elem-02-t"):
        (suite / "svg" / f"{name}.svg").write_text(picture, encoding="utf-8")
        (suite / "png" / f"{name}.png").write_bytes(svg_conformance.render_resvg(picture, 200, 150))
    return suite


def test_check_test_can_score_against_resvg_instead_of_the_reference_image(tmp_path):
    suite = _fake_suite(tmp_path)
    (suite / "png" / "shapes-rect-01-t.png").write_bytes(
        svg_conformance.render_resvg(_PICTURE.format(x=120, extra=""), 200, 150)
    )
    assert svg_conformance.check_test(suite, "shapes-rect-01-t")[0].status == "differs"
    result, _doc = svg_conformance.check_test(suite, "shapes-rect-01-t", reference="resvg")
    assert result.status == "match"


def test_check_suite_uses_each_tests_reference(tmp_path):
    suite = _fake_suite(tmp_path)
    (suite / "png" / "shapes-rect-01-t.png").write_bytes(
        svg_conformance.render_resvg(_PICTURE.format(x=120, extra=""), 200, 150)
    )
    results = svg_conformance.check_suite(suite, "shapes-rect-0*", references={"shapes-rect-01-t": "resvg"})
    assert {result.name: result.status for result in results} == {
        "shapes-rect-01-t": "match",
        "shapes-rect-02-t": "match",
    }


def test_report_shows_the_reason_for_resvg_checked_tests(tmp_path):
    suite = _fake_suite(tmp_path)
    listed = {
        "shapes-rect-01-t": svg_conformance.PassEntry("shapes-rect-01-t", 0.03, "reference is outdated", True, "resvg")
    }
    folder = tmp_path / "report"
    (folder / "sheets").mkdir(parents=True)
    page = svg_conformance.write_report([_result("shapes-rect-01-t")], suite, listed, folder).read_text(
        encoding="utf-8"
    )
    assert "checked against resvg: reference is outdated" in page


def test_report_has_tables_rows_and_sheets_for_in_scope_differences(tmp_path):
    suite = _fake_suite(tmp_path)
    results = [
        _result("shapes-rect-01-t"),
        _result("shapes-rect-02-t", "differs", 0.2, notes=("1 <gradient> was painted grey",)),
        _result("animate-elem-02-t", "differs", 0.3),
    ]
    folder = tmp_path / "report"
    (folder / "sheets").mkdir(parents=True)
    (folder / "sheets" / "stale.png").write_bytes(b"old")
    index = svg_conformance.write_report(results, suite, LISTED, folder)
    page = index.read_text(encoding="utf-8")
    assert sorted(path.name for path in (folder / "sheets").iterdir()) == ["shapes-rect-02-t.png"]
    sheet = svg_conformance.decoded((folder / "sheets" / "shapes-rect-02-t.png").read_bytes())
    assert (sheet.width(), sheet.height()) == (3 * 200 + 2 * 8, 150)
    assert "1 &lt;gradient&gt; was painted grey" in page
    assert 'href="sheets/shapes-rect-02-t.png"' in page
    assert "animate (1)" in page
    assert "<script" not in page


# --- With the fetched suite ---------------------------------------------------------------------

PASS_LIST = svg_conformance.passing(svg_conformance.read_pass_list())


@pytest.fixture(scope="module")
def suite() -> Path:
    folder = svg_conformance.suite_folder()
    if folder is None:
        pytest.skip(f"W3C SVG suite not fetched; {svg_conformance.FETCH_HINT}")
    return folder


def test_pass_list_names_exist(suite):
    missing = sorted(set(svg_conformance.read_pass_list()) - set(svg_conformance.suite_tests(suite)))
    assert not missing, f"not in the suite: {missing}"


def test_pass_list_has_only_in_scope_tests():
    assert [name for name in svg_conformance.read_pass_list() if not svg_conformance.in_scope(name)] == []


@pytest.mark.parametrize("entry", PASS_LIST.values(), ids=list(PASS_LIST))
def test_listed_test_still_matches(suite, entry):
    result, _doc = svg_conformance.check_test(suite, entry.name, entry.threshold, entry.reference)
    assert result.status == "match", (
        f"{entry.name}: {result.status}, score {result.score}, threshold {entry.threshold}, "
        f"error {result.error}, notes {list(result.notes)}"
    )


@pytest.mark.parametrize("entry", PASS_LIST.values(), ids=list(PASS_LIST))
def test_listed_test_saves_for_other_viewers(suite, entry):
    _result, doc = svg_conformance.check_test(suite, entry.name, entry.threshold, entry.reference)
    assert svg_conformance.check_generator(doc) < svg_conformance.THRESHOLD


@pytest.mark.parametrize("entry", PASS_LIST.values(), ids=list(PASS_LIST))
def test_listed_test_survives_p2s_and_svg_round_trips(suite, entry):
    from presstoshape.formats.p2s import SavedState, read_p2s, write_p2s
    from presstoshape.formats.svg import write_svg

    _result, doc = svg_conformance.check_test(suite, entry.name, entry.threshold, entry.reference)
    reopened, _state = read_p2s(write_p2s(doc, SavedState(), None, "test"))
    assert reopened == doc
    assert write_svg(reopened) == write_svg(doc)
    assert write_svg(read_svg(write_svg(doc))) == write_svg(read_svg(write_svg(reopened)))
