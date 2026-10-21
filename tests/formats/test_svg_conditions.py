"""systemLanguage, requiredExtensions and <switch> choices."""

import xml.etree.ElementTree as ET

import pytest

from presstoshape.formats.svg_conditions import passes, switch_choice

NS = 'xmlns="http://www.w3.org/2000/svg"'


def _el(attributes: str) -> ET.Element:
    return ET.fromstring(f"<g {NS} {attributes}/>")


@pytest.mark.parametrize(
    ("value", "languages", "expected"),
    [
        ("en", ("en",), True),
        ("EN", ("en",), True),
        ("en-US", ("en",), True),
        ("en", ("en-US",), False),
        ("de, en", ("en",), True),
        ("de , fr", ("en",), False),
        ("english", ("en",), False),
        ("", ("en",), False),
        ("fr", ("de", "en"), False),
        ("de-AT", ("de", "en"), True),
    ],
)
def test_system_language(value, languages, expected):
    assert passes(_el(f'systemLanguage="{value}"'), languages) is expected


def test_no_conditions_pass_and_extensions_never_do():
    assert passes(_el(""), ("en",))
    assert not passes(_el('requiredExtensions="http://example.org/x"'), ("en",))
    assert not passes(_el('requiredExtensions=""'), ("en",))


def test_required_features_are_ignored():
    assert passes(_el('requiredFeatures="http://www.w3.org/TR/SVG11/feature#Nothing"'), ("en",))


def _switch(body: str) -> ET.Element:
    return ET.fromstring(f"<switch {NS}>{body}</switch>")


def test_switch_chooses_the_first_passing_drawable_child():
    switch = _switch(
        '<title/><text systemLanguage="de" id="de"/><text systemLanguage="en" id="en"/><text id="any"/>'
    )
    assert switch_choice(switch, ("de", "en")).get("id") == "de"
    assert switch_choice(switch, ("en",)).get("id") == "en"
    assert switch_choice(switch, ("fr",)).get("id") == "any"


def test_switch_skips_non_drawable_and_failing_children_and_may_choose_nothing():
    switch = _switch('<desc/><linearGradient/><rect systemLanguage="de" id="x"/><foreignObject requiredExtensions="e"/>')
    assert switch_choice(switch, ("en",)) is None
