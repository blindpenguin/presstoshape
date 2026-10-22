import time
import xml.etree.ElementTree as ET

from presstoshape.formats.css import parse, parse_declarations
from presstoshape.formats.svg_nodes import Nodes


def _for(sheet, tag="path", element_id=None, classes=()):
    attributes = {"class": " ".join(classes)} if classes else {}
    if element_id is not None:
        attributes["id"] = element_id
    element = ET.Element(f"{{http://www.w3.org/2000/svg}}{tag}", attributes)
    root = ET.Element("{http://www.w3.org/2000/svg}svg")
    root.append(element)
    return sheet.declarations_for(Nodes(root).node(element))


def test_illustrator_style_class_rules():
    sheet = parse(".st0{fill:#E30613;}\n.st1{fill:none;stroke:#000000;stroke-width:2;}")
    assert _for(sheet, classes=["st0"]) == ({"fill": "#E30613"}, {})
    assert _for(sheet, classes=["st1"])[0] == {"fill": "none", "stroke": "#000000", "stroke-width": "2"}
    assert _for(sheet, classes=["other"]) == ({}, {})


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
    sheet = parse("rect::before, .x { fill: red }")
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


def test_media_blocks_for_screen_and_all_are_entered():
    sheet = parse(
        "@media screen { .a { fill: red } } @media all { .b { fill: green } } @media { .c { fill: blue } }"
        "@media print, screen { .d { fill: black } } @media (min-width: 10px) { .e { fill: white } } .f { fill: pink }"
    )
    assert [_for(sheet, classes=[name])[0] for name in "abcd"] == [
        {"fill": "red"},
        {"fill": "green"},
        {"fill": "blue"},
        {"fill": "black"},
    ]
    assert _for(sheet, classes=["e"]) == ({}, {})
    assert _for(sheet, classes=["f"])[0] == {"fill": "pink"}
    assert sheet.skipped == 1


def test_rules_inside_media_keep_source_order():
    sheet = parse(".a { fill: red } @media screen { .a { fill: green } } .a { stroke: blue }")
    assert _for(sheet, classes=["a"])[0] == {"fill": "green", "stroke": "blue"}


def test_combinators_apply():
    root = ET.fromstring(
        '<svg xmlns="http://www.w3.org/2000/svg"><g class="icon"><path id="in"/></g><path id="out"/></svg>'
    )
    nodes = Nodes(root)
    sheet = parse("g.icon > path { fill: red }")
    inside, outside = root[0][0], root[1]
    assert sheet.declarations_for(nodes.node(inside))[0] == {"fill": "red"}
    assert sheet.declarations_for(nodes.node(outside)) == ({}, {})
