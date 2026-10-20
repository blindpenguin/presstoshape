import time

import pytest

from presstoshape.formats.css import Compound, parse, parse_declarations, parse_selector


def _for(sheet, tag="path", element_id=None, classes=()):
    return sheet.declarations_for(tag, element_id, frozenset(classes))


def test_illustrator_style_class_rules():
    sheet = parse(".st0{fill:#E30613;}\n.st1{fill:none;stroke:#000000;stroke-width:2;}")
    assert _for(sheet, classes=["st0"]) == ({"fill": "#E30613"}, {})
    assert _for(sheet, classes=["st1"])[0] == {"fill": "none", "stroke": "#000000", "stroke-width": "2"}
    assert _for(sheet, classes=["other"]) == ({}, {})


@pytest.mark.parametrize(
    "text, expected",
    [
        ("rect", Compound("rect", frozenset(), frozenset())),
        ("*", Compound(None, frozenset(), frozenset())),
        ("#logo", Compound(None, frozenset({"logo"}), frozenset())),
        ("path.st0", Compound("path", frozenset(), frozenset({"st0"}))),
        (".a.b", Compound(None, frozenset(), frozenset({"a", "b"}))),
        ("  g#x.y  ", Compound("g", frozenset({"x"}), frozenset({"y"}))),
    ],
)
def test_supported_selectors(text, expected):
    assert parse_selector(text) == expected


@pytest.mark.parametrize("text", ["g rect", "g > rect", "a + b", "a ~ b", "[fill]", "a:hover", "", "svg|rect", "1x"])
def test_unsupported_selectors(text):
    assert parse_selector(text) is None


def test_compound_selectors_need_every_part():
    sheet = parse("path.a.b { fill: red }")
    assert _for(sheet, classes=["a", "b", "c"])[0] == {"fill": "red"}
    assert _for(sheet, classes=["a"]) == ({}, {})
    assert _for(sheet, tag="rect", classes=["a", "b"]) == ({}, {})


def test_selector_lists_apply_to_each_selector():
    sheet = parse("rect, .x, #y { fill: red }")
    assert _for(sheet, tag="rect")[0] == {"fill": "red"}
    assert _for(sheet, classes=["x"])[0] == {"fill": "red"}
    assert _for(sheet, element_id="y")[0] == {"fill": "red"}


def test_unsupported_selectors_in_a_list_skip_only_themselves():
    sheet = parse("g rect, .x { fill: red }")
    assert sheet.skipped == 1
    assert _for(sheet, classes=["x"])[0] == {"fill": "red"}


def test_specificity_beats_order():
    sheet = parse("#a { fill: red } .b { fill: green } path { fill: blue }")
    assert _for(sheet, element_id="a", classes=["b"])[0] == {"fill": "red"}
    assert _for(sheet, classes=["b"])[0] == {"fill": "green"}


def test_later_rule_wins_at_equal_specificity():
    sheet = parse(".a { fill: red; stroke: red } .b { fill: green }")
    assert _for(sheet, classes=["a", "b"])[0] == {"fill": "green", "stroke": "red"}


def test_important_is_separate():
    sheet = parse("#a { fill: red } .b { fill: green !important; stroke: blue ! IMPORTANT }")
    normal, important = _for(sheet, element_id="a", classes=["b"])
    assert normal == {"fill": "red"}
    assert important == {"fill": "green", "stroke": "blue"}


def test_comments_and_html_markers_are_ignored():
    sheet = parse("<!-- /* .x { fill: red } */ .y { /* note */ fill: green } -->")
    assert _for(sheet, classes=["x"]) == ({}, {})
    assert _for(sheet, classes=["y"])[0] == {"fill": "green"}
    assert sheet.skipped == 0


def test_at_rules_are_skipped_and_counted():
    sheet = parse(
        '@import url("x.css");\n@font-face { font-family: X; src: url(x.woff) }\n'
        "@media print { .a { fill: red } }\n.b { fill: green }"
    )
    assert sheet.skipped == 3
    assert _for(sheet, classes=["a"]) == ({}, {})
    assert _for(sheet, classes=["b"])[0] == {"fill": "green"}


def test_malformed_input_recovers_at_the_next_rule():
    sheet = parse(".a { fill: red } } .b { fill green; stroke: blue } .c { fill: ")
    assert _for(sheet, classes=["a"])[0] == {"fill": "red"}
    assert _for(sheet, classes=["b"])[0] == {"stroke": "blue"}
    assert _for(sheet, classes=["c"]) == ({}, {})


def test_garbage_never_raises():
    for text in ["{", "}", "{{}}", "@", "@media {", ".a {", ";;;", "a{b}", ".a { : ; fill: }"]:
        parse(text)


def test_declarations_keep_semicolons_inside_parentheses_and_quotes():
    declarations = parse_declarations("fill: url(\"a;b\"); font-family: 'x;y'; Stroke : red")
    assert declarations == (("fill", 'url("a;b")', False), ("font-family", "'x;y'", False), ("stroke", "red", False))


def test_many_rules_are_looked_up_quickly():
    sheet = parse("\n".join(f".c{index} {{ fill: #{index:06x} }}" for index in range(500)))
    start = time.perf_counter()
    for index in range(10_000):
        _for(sheet, classes=[f"c{index % 500}"])
    assert time.perf_counter() - start < 0.5
