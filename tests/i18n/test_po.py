import pytest

from presstoshape.i18n import po
from presstoshape.i18n.po import Entry, PoError, fields, parse_po, write_po

HEADER = """msgid ""
msgstr ""
"Language: de\\n"
"Plural-Forms: nplurals=2; plural=(n != 1);\\n"
"""


def _parse(body: str, header: str = HEADER):
    return parse_po(header + "\n" + body, "test.po")


def test_header_language_and_plural_rule():
    parsed = _parse("")
    assert parsed.language == "de"
    assert parsed.plural_rule.count == 2
    assert parsed.entries == ()


def test_entries_contexts_plurals_comments_and_multiline():
    parsed = _parse(
        r"""
# translator comment
#. extracted comment
#: presstoshape/a.py:3 presstoshape/b.py:9
msgid "&Delete"
msgstr "&Löschen"

msgctxt "part mode"
msgid "Add"
msgstr "Hinzufügen"

msgid "Copied {count} object"
msgid_plural "Copied {count} objects"
msgstr[0] "{count} Objekt kopiert"
msgstr[1] ""
"{count} Objekte kopiert"

msgid "Tab\tand \"quotes\" \\ and\nnewline"
msgstr "Tab\tund \"Anführung\" \\ und\nZeilenumbruch"
"""
    )
    delete, add, copied, escaped = parsed.entries
    assert delete == Entry(None, "&Delete", None, ("&Löschen",), False, ("presstoshape/a.py:3", "presstoshape/b.py:9"))
    assert add.key == ("part mode", "Add")
    assert copied.plural == "Copied {count} objects"
    assert copied.translations == ("{count} Objekt kopiert", "{count} Objekte kopiert")
    assert escaped.message == 'Tab\tand "quotes" \\ and\nnewline'
    assert escaped.translations == ('Tab\tund "Anführung" \\ und\nZeilenumbruch',)
    assert all(entry.translated for entry in parsed.entries)


def test_fuzzy_and_empty_entries_are_untranslated_and_obsolete_ones_skipped():
    parsed = _parse(
        """
#, fuzzy, python-format
msgid "Open"
msgstr "Öffnen"

msgid "Save"
msgstr ""

#~ msgid "Gone"
#~ msgstr "Weg"
"""
    )
    assert [(entry.message, entry.fuzzy, entry.translated) for entry in parsed.entries] == [
        ("Open", True, False),
        ("Save", False, False),
    ]


@pytest.mark.parametrize(
    "body, line",
    [
        ('msgid "a"\nmsgstr "b"\nbogus "x"', 8),
        ('msgid "a"\nmsgstr "b', 7),
        ('msgid "a"\nmsgstr "b\\q"', 7),
        ('msgid "a"\nmsgstr "b"x"', 7),
        ('msgid "a"\nmsgid "b"\nmsgstr ""', 6),
        ('msgid "a"\nmsgid_plural "as"\nmsgstr "x"', 6),
        ('msgid "a"\nmsgid_plural "as"\nmsgstr[0] "x"\nmsgstr[2] "y"', 6),
        ('msgstr "x"', 6),
        ('msgid "a"\nmsgstr "b"\n\nmsgid "a"\nmsgstr "c"', 9),
    ],
)
def test_broken_syntax_names_the_line(body, line):
    with pytest.raises(PoError, match=f"line {line}"):
        _parse(body)


def test_string_outside_an_entry_names_the_line():
    with pytest.raises(PoError, match="line 2"):
        parse_po('# comment\n"floating"\n', "test.po")


@pytest.mark.parametrize(
    "header",
    ['msgid ""\nmsgstr ""\n"Language: de\\n"\n', 'msgid ""\nmsgstr ""\n"Plural-Forms: nplurals=2; plural=n !!;\\n"\n'],
)
def test_missing_or_invalid_plural_forms_is_refused(header):
    with pytest.raises(PoError, match="test.po"):
        _parse('msgid "a"\nmsgstr "b"', header)


def test_templates_need_no_plural_forms():
    parsed = parse_po('msgid ""\nmsgstr ""\n\nmsgid "a"\nmsgstr ""\n', "presstoshape.pot", template=True)
    assert [entry.message for entry in parsed.entries] == ["a"]


def test_size_limit(monkeypatch):
    monkeypatch.setattr(po, "MAX_CHARACTERS", 10)
    with pytest.raises(PoError, match="too large"):
        _parse("")


def test_placeholder_rules():
    parsed = _parse(
        """
msgid "Moved {count} object"
msgstr "{cout} verschoben"

msgid "Rotate {angle:.1f}°"
msgstr "Drehen {angle}°"

msgid "Layer {number}"
msgstr "Ebene {number"

msgid "Hello {name}"
msgstr "Hallo {name}"

msgid "Copied {count} object"
msgid_plural "Copied {count} objects"
msgstr[0] "Ein Objekt kopiert"
msgstr[1] "{count} Objekte kopiert"

msgid "Deleted {count} object"
msgid_plural "Deleted {count} objects"
msgstr[0] "{count} {extra}"
msgstr[1] "{count}"

msgid "One form"
msgid_plural "Forms"
msgstr[0] "Nur eine"
"""
    )
    assert [entry.message for entry in parsed.entries] == ["Hello {name}", "Copied {count} object"]
    assert len(parsed.ignored) == 5
    assert parsed.ignored[0].startswith("line 7:")
    assert "plural forms" in parsed.ignored[-1]


def test_fields_include_spec_and_conversion():
    assert fields("{a} {b!r} {c:.2f}") == {("a", "", None), ("b", "", "r"), ("c", ".2f", None)}
    with pytest.raises(ValueError):
        fields("{a")


def test_write_then_parse_round_trips():
    entries = [
        Entry(None, "&Delete", None, ("&Löschen",), references=("presstoshape/a.py:3",)),
        Entry("part mode", "Add", None, ("Hinzufügen",), fuzzy=True),
        Entry(None, "Copied {count} object", "Copied {count} objects", ("{count} Objekt", "{count} Objekte")),
        Entry(None, 'Say "hi"\n\tthere\\', None, ("",)),
    ]
    header = {"Language": "de", "Plural-Forms": "nplurals=2; plural=(n != 1);"}
    text = write_po(header, entries, obsolete=[Entry(None, "Gone", None, ("Weg",))])
    parsed = parse_po(text, "round.po")
    assert parsed.entries == tuple(entries)
    assert dict(parsed.header) == header
    assert '#~ msgid "Gone"' in text
