import pytest

from presstoshape.i18n.plural import ENGLISH, PluralError, parse_plural_forms

# Formulas as published by gettext / Unicode CLDR-based tooling.
GERMAN = "nplurals=2; plural=(n != 1);"
FRENCH = "nplurals=2; plural=(n > 1);"
POLISH = "nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"
RUSSIAN = (
    "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"
)
ARABIC = (
    "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5);"
)


@pytest.mark.parametrize(
    "header, expected",
    [
        (GERMAN, {0: 1, 1: 0, 2: 1, 5: 1, 21: 1}),
        (FRENCH, {0: 0, 1: 0, 2: 1, 100: 1}),
        (POLISH, {1: 0, 2: 1, 4: 1, 5: 2, 12: 2, 22: 1, 25: 2, 112: 2, 122: 1}),
        (RUSSIAN, {1: 0, 11: 2, 21: 0, 2: 1, 12: 2, 22: 1, 5: 2, 111: 2, 101: 0}),
        (ARABIC, {0: 0, 1: 1, 2: 2, 3: 3, 10: 3, 11: 4, 99: 4, 100: 5, 102: 5, 103: 3}),
    ],
)
def test_known_formulas_choose_the_right_form(header, expected):
    rule = parse_plural_forms(header)
    assert {n: rule.choose(n) for n in expected} == expected


def test_english_default():
    assert [ENGLISH.choose(n) for n in (0, 1, 2)] == [1, 0, 1]


def test_single_form_languages_and_c_operators():
    assert parse_plural_forms("nplurals=1; plural=0;").choose(7) == 0
    rule = parse_plural_forms("nplurals=3; plural=!(n - 1) ? 0 : -n + 10 * 2 / 4 % 3 == 2 ? 1 : 2")
    assert rule.choose(1) == 0
    # -3 + (20 / 4) % 3 = -3 + 2 = -1 -> not 2 -> form 2
    assert rule.choose(3) == 2


def test_c_division_truncates_and_zero_division_gives_form_zero():
    rule = parse_plural_forms("nplurals=3; plural=(0 - n) / 2 == -1 ? 1 : 2;")
    assert rule.choose(3) == 1
    assert parse_plural_forms("nplurals=2; plural=1 / (n - 1);").choose(1) == 0


def test_out_of_range_result_falls_back_to_form_zero():
    assert parse_plural_forms("nplurals=2; plural=n;").choose(5) == 0


@pytest.mark.parametrize(
    "header",
    [
        "",
        "plural=(n != 1);",
        "nplurals=2;",
        "nplurals=0; plural=0;",
        "nplurals=9; plural=0;",
        "nplurals=2; plural=(n != 1;",
        "nplurals=2; plural=n !== 1;",
        "nplurals=2; plural=__import__('os');",
        "nplurals=2; plural=n ? 1;",
        "nplurals=2; plural=x;",
        "nplurals=2; plural=" + "(" * 60 + "n" + ")" * 60 + ";",
        "nplurals=2; plural=" + "n+" * 300 + "1;",
    ],
)
def test_malformed_or_hostile_formulas_are_refused(header):
    with pytest.raises(PluralError):
        parse_plural_forms(header)
