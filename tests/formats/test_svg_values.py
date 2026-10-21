"""Path data and point lists: valid prefixes, packed flags, errors."""

from unittest import mock

import pytest

from presstoshape.formats.svg_values import parse_path_data, parse_points, valid_path_prefix
from presstoshape.models.shapes import CubicTo, LineTo, MoveTo


@pytest.mark.parametrize(
    "data",
    [
        "M 10 10 L 20 20 Z",
        "M10,10L20,20",
        "m1-2.5.5e2 3",
        "M0 0 10 10 20 20",
        "M0 0 L 1 1, 2 2",
        "M0 0 C1 2 3 4 5 6 7 8 9 10 11 12",
        "M0 0 A5 5 0 00 10 10",
        "M0 0 A5 5 0 1,1 10 10 a2 2 0 0110 10",
        "M0 0 H5 V5 z",
        "M0 0 Z M5 5 Z",
        "  M 1 1  ",
    ],
)
def test_complete_path_data_is_unchanged(data):
    assert valid_path_prefix(data) == (data.rstrip(), False)


@pytest.mark.parametrize(
    ("data", "prefix"),
    [
        ("M 10 10 L 20", "M 10 10"),
        ("M 10 10 L 20 20 L", "M 10 10 L 20 20"),
        ("M 10 10 L 20 20 X 5 5", "M 10 10 L 20 20"),
        ("M 10 10 L 20 20 30", "M 10 10 L 20 20"),
        ("M 10 10 L 20 20 30 40 50", "M 10 10 L 20 20 30 40"),
        ("M 10 10 A5 5 0 2 0 20 20", "M 10 10"),
        ("M0 0 L 5 5 Z 7 7", "M0 0 L 5 5 Z"),
        ("M0 0 L 5 5 , L 6 6", "M0 0 L 5 5"),
        ("M0 0 L 1e 5", "M0 0"),
        ("M0 0 L 1 1 ,", "M0 0 L 1 1"),
    ],
)
def test_path_data_is_cut_at_the_first_error(data, prefix):
    assert valid_path_prefix(data) == (prefix, True)


@pytest.mark.parametrize("data", ["L 10 10", "10 10", "X", "M", "M 10"])
def test_path_data_without_a_valid_start_is_empty(data):
    assert valid_path_prefix(data) == ("", True)


def test_empty_path_data_is_not_an_error():
    assert valid_path_prefix("") == ("", False)
    assert valid_path_prefix("  \n") == ("", False)


def test_adversarial_path_data_is_scanned_quickly():
    assert valid_path_prefix("M0 0" + "1" * 200_000 + "e")[1] is True
    assert valid_path_prefix("M0 0 " + "L 1 1 " * 50_000 + "L")[1] is True


def test_parse_path_data_keeps_the_valid_part():
    segments, cut = parse_path_data("M 10 10 L 20 20 L 30")
    assert segments == (MoveTo(10, 10), LineTo(20, 20))
    assert cut is True


def test_parse_path_data_complete():
    segments, cut = parse_path_data("M0 0 C1 2 3 4 5 6")
    assert segments == (MoveTo(0, 0), CubicTo(1, 2, 3, 4, 5, 6))
    assert cut is False


def test_packed_arc_flags_parse():
    segments, cut = parse_path_data("M0 0 a5 5 0 0110 10")
    assert cut is False
    assert len(segments) > 1 and segments[-1].x == pytest.approx(10)


def test_nothing_valid_gives_no_segments():
    assert parse_path_data("hello") == ((), True)
    assert parse_path_data("") == ((), False)


def test_svgelements_failure_on_a_valid_prefix_is_a_broken_path():
    with mock.patch("presstoshape.formats.svg_values.se.Path", side_effect=ValueError):
        assert parse_path_data("M0 0 L1 1") == ((), True)


def test_points():
    assert parse_points("1,2 3,4") == (((1, 2), (3, 4)), False)
    assert parse_points("  1 2\n3 4  ") == (((1, 2), (3, 4)), False)
    assert parse_points("1,2 3,4 x 5,6") == (((1, 2), (3, 4)), True)
    assert parse_points("1,2 3") == (((1, 2),), True)
    assert parse_points("") == ((), False)


def _built(*chunks: tuple[str, bool]) -> str:
    from presstoshape.formats.svg_values import Whitespace

    builder = Whitespace()
    for text, preserve in chunks:
        builder.add(text, preserve)
    return builder.result()


def test_default_whitespace_removes_breaks_and_collapses():
    assert _built(("  Hello\n   big \t\t world  ", False)) == "Hello big world"
    assert _built(("a\nb", False)) == "ab"
    assert _built(("\n  ", False)) == ""


def test_preserve_whitespace_keeps_every_space_and_turns_breaks_into_spaces():
    assert _built(("  two  spaces \n\tend ", True)) == "  two  spaces   end "


def test_boundaries_between_chunks_neither_lose_nor_double_spaces():
    assert _built(("a ", False), (" b", False)) == "a b"
    assert _built(("a", False), (" ", False), ("b", False)) == "a b"
    assert _built(("a ", True), (" b", False)) == "a  b"
    assert _built(("a", False), ("  b ", True)) == "a  b "
    assert _built(("a ", False), ("b  ", True)) == "a b  "
    assert _built((" ", False), ("a", False)) == "a"
