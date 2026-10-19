import importlib.util
from pathlib import Path

import pytest

from presstoshape.i18n.po import Entry, parse_po, write_po

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "update_translations.py"
_spec = importlib.util.spec_from_file_location("update_translations", _SCRIPT)
update_translations = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(update_translations)


def test_committed_template_and_translations_are_up_to_date():
    assert update_translations.run(check=True) == 0, "run: uv run python scripts/update_translations.py"


def _module(tmp_path, code: str) -> Path:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "mod.py").write_text(code, encoding="utf-8")
    return package


def test_extracts_every_call_type_with_references_in_order(tmp_path):
    package = _module(
        tmp_path,
        "LABEL = N_('&Delete')\n"
        "def f(n):\n"
        "    _('Hello ' 'world')\n"
        "    ngettext('{count} object', '{count} objects', n)\n"
        "    pgettext('part mode', 'Add')\n"
        "    npgettext('files', '{count} file', '{count} files', n)\n"
        "    _('&Delete')\n",
    )
    entries = update_translations.extract(package, tmp_path)
    assert [(entry.context, entry.message, entry.plural) for entry in entries] == [
        (None, "&Delete", None),
        (None, "Hello world", None),
        (None, "{count} object", "{count} objects"),
        ("part mode", "Add", None),
        ("files", "{count} file", "{count} files"),
    ]
    assert entries[0].references == ("pkg/mod.py",)


@pytest.mark.parametrize(
    "call",
    ["_(f'Moved {n}')", "_('a' + name)", "_('{x}'.format(x=n))", "_('%d' % n)", "_(message='a')", "_()"],
)
def test_non_literal_texts_are_errors(tmp_path, call):
    package = _module(tmp_path, f"def f(n, name, plural):\n    {call}\n")
    with pytest.raises(update_translations.ExtractionError, match="pkg/mod.py:2"):
        update_translations.extract(package, tmp_path)


def test_merge_keeps_translations_adds_new_and_obsoletes_gone_ones():
    header = {"Language": "de", "Plural-Forms": "nplurals=2; plural=(n != 1);"}
    old = write_po(
        header,
        [
            Entry(None, "Open", None, ("Öffnen",)),
            Entry(None, "Gone", None, ("Weg",)),
            Entry(None, "{count} object", "{count} objects", ("{count} Objekt", "{count} Objekte")),
        ],
    )
    template = [
        Entry(None, "Open", None, ("",), references=("a.py:1",)),
        Entry(None, "{count} object", "{count} objects", ("", ""), references=("a.py:2",)),
        Entry(None, "New", None, ("",), references=("a.py:3",)),
    ]
    merged_text = update_translations.merge(template, old, "de.po")
    merged = parse_po(merged_text, "de.po")
    assert [(entry.message, entry.translations, entry.references) for entry in merged.entries] == [
        ("Open", ("Öffnen",), ("a.py:1",)),
        ("{count} object", ("{count} Objekt", "{count} Objekte"), ("a.py:2",)),
        ("New", ("",), ("a.py:3",)),
    ]
    assert '#~ msgid "Gone"' in merged_text
    assert dict(merged.header) == header


def test_variables_holding_marked_texts_are_allowed(tmp_path):
    package = _module(tmp_path, "NAME = N_('Union')\ndef f(label):\n    return _(label), _(NAME)\n")
    assert [entry.message for entry in update_translations.extract(package, tmp_path)] == ["Union"]
