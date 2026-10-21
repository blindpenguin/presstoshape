"""Selector parsing, specificity and matching on small documents."""

import time
import xml.etree.ElementTree as ET

import pytest

from presstoshape.formats.css_selectors import parse_selector
from presstoshape.formats.svg_nodes import Nodes

NS = 'xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"'
DOCUMENT = f"""
<svg {NS} id="root" xml:lang="en-GB">
  <g id="a" class="icon big">
    <rect id="r1" class="x" fill="red" data-n="a-b"/>
    <rect id="r2" class="y"/>
    <circle id="c1"/>
    <g id="inner" lang="de"><path id="p1" class="x"/></g>
  </g>
  <a id="link" xlink:href="#a"><rect id="r3"/></a>
  <path id="p2"/>
</svg>
"""


@pytest.fixture
def doc():
    root = ET.fromstring(DOCUMENT)
    nodes = Nodes(root)
    elements = {element.get("id"): nodes.node(element) for element in root.iter() if element.get("id")}
    return elements


def _matches(doc, selector, *ids):
    parsed = parse_selector(selector)
    assert parsed is not None, selector
    return sorted(name for name, node in doc.items() if parsed.matches(node)) == sorted(ids)


def test_simple_selectors(doc):
    assert _matches(doc, "rect", "r1", "r2", "r3")
    assert _matches(doc, "#c1", "c1")
    assert _matches(doc, ".x", "r1", "p1")
    assert _matches(doc, "rect.x", "r1")
    assert _matches(doc, ".icon.big", "a")
    assert _matches(doc, ".icon.small")


def test_universal_matches_everything(doc):
    assert _matches(doc, "*", *doc)


def test_combinators(doc):
    assert _matches(doc, "g rect", "r1", "r2")
    assert _matches(doc, "g path", "p1")
    assert _matches(doc, "#a > rect", "r1", "r2")
    assert _matches(doc, "#a > path")
    assert _matches(doc, "#a path", "p1")
    assert _matches(doc, "rect + rect", "r2")
    assert _matches(doc, "rect + circle", "c1")
    assert _matches(doc, "rect ~ g", "inner")
    assert _matches(doc, "rect~circle", "c1")
    assert _matches(doc, "g>rect.x", "r1")
    assert _matches(doc, ".icon   >   .y", "r2")


@pytest.mark.parametrize(
    ("selector", "ids"),
    [
        ("[fill]", ["r1"]),
        ("[fill=red]", ["r1"]),
        ('[fill="red"]', ["r1"]),
        ("[fill=blue]", []),
        ("[class~=big]", ["a"]),
        ("[data-n|=a]", ["r1"]),
        ("[id^=r]", ["r1", "r2", "r3", "root"]),
        ("[id$=1]", ["c1", "p1", "r1"]),
        ("[id*=nn]", ["inner"]),
    ],
)
def test_attribute_selectors(doc, selector, ids):
    assert _matches(doc, selector, *ids)


def test_structural_pseudo_classes(doc):
    assert _matches(doc, "rect:first-child", "r1", "r3")
    assert _matches(doc, "g > :last-child", "inner", "p1")
    assert _matches(doc, "rect:only-child", "r3")
    assert _matches(doc, ":root", "root")
    assert _matches(doc, "#a > :nth-child(2)", "r2")
    assert _matches(doc, "#a > :nth-child(odd)", "r1", "c1")
    assert _matches(doc, "#a > :nth-child(even)", "r2", "inner")
    assert _matches(doc, "#a > :nth-child(2n+3)", "c1")
    assert _matches(doc, "#a > :nth-child(-n+2)", "r1", "r2")
    assert _matches(doc, "#a > :nth-child( n )", "r1", "r2", "c1", "inner")
    assert _matches(doc, "#a > :nth-child(0n+4)", "inner")


def test_not_lang_link_and_never(doc):
    assert _matches(doc, "#a > :not(.x):not(circle)", "r2", "inner")
    assert _matches(doc, "path:lang(de)", "p1")
    assert _matches(doc, "rect:lang(en)", "r1", "r2", "r3")
    assert _matches(doc, "a:link", "link")
    assert _matches(doc, "rect:hover")


def test_specificity():
    assert parse_selector("rect").specificity == (0, 0, 1)
    assert parse_selector("#a .b rect").specificity == (1, 1, 1)
    assert parse_selector("g > path.x[fill]:first-child").specificity == (0, 3, 2)
    assert parse_selector(":not(#a)").specificity == (1, 0, 0)
    assert parse_selector("*").specificity == (0, 0, 0)


@pytest.mark.parametrize(
    "text",
    ["", "rect::before", "rect:before", "a:unknown", "svg|rect", "a >", "> a", "a ,b", "[", "[a=]", ":nth-child(x)", "1x", "a)", ".", "#"],
)
def test_unsupported_selectors(text):
    assert parse_selector(text) is None


def test_whitespace_around_is_ignored():
    assert parse_selector("  g  rect \n") is not None


def test_adversarial_long_selectors_parse_quickly():
    start = time.perf_counter()
    for text in ("a " * 5000, "a" * 10_000, "[" * 10_000, ":not(" * 5000, "a>" * 5000, "." + "a-" * 5000):
        parse_selector(text)
    assert time.perf_counter() - start < 0.5


def test_long_descendant_chains_are_refused():
    assert parse_selector(" ".join(["a"] * 40)) is None
