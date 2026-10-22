from presstoshape import i18n
from presstoshape.i18n import N_, _, ngettext, npgettext, pgettext
from presstoshape.i18n.catalog import Catalog, build_catalog
from presstoshape.i18n.po import parse_po


def _po(body: str, plural_forms: str = "nplurals=2; plural=(n != 1);"):
    header = f'msgid ""\nmsgstr ""\n"Plural-Forms: {plural_forms}\\n"\n\n'
    return parse_po(header + body, "test.po")


SHIPPED = _po(
    """msgid "Open"
msgstr "Öffnen"

msgid "Save"
msgstr "Speichern"

msgctxt "part mode"
msgid "Add"
msgstr "Hinzufügen"

msgid "Copied {count} object"
msgid_plural "Copied {count} objects"
msgstr[0] "{count} Objekt kopiert"
msgstr[1] "{count} Objekte kopiert"
"""
)


def test_without_install_everything_is_english():
    assert _("Open") == "Open"
    assert ngettext("{count} object", "{count} objects", 1) == "{count} object"
    assert ngettext("{count} object", "{count} objects", 0) == "{count} objects"
    assert N_("&Delete") == "&Delete"
    assert i18n.active_language() == "en"


def test_installed_catalog_translates_with_contexts_and_plurals():
    i18n.install(build_catalog("de", [SHIPPED]))
    assert i18n.active_language() == "de"
    assert _("Open") == "Öffnen"
    assert _("Add") == "Add"
    assert pgettext("part mode", "Add") == "Hinzufügen"
    copied = ngettext("Copied {count} object", "Copied {count} objects", 3).format(count=3)
    assert copied == "3 Objekte kopiert"
    assert npgettext("other", "Copied {count} object", "Copied {count} objects", 1) == "Copied {count} object"
    assert _("Unknown") == "Unknown"


def test_user_file_overrides_entry_by_entry_and_untranslated_entries_dont_hide_shipped_ones():
    user = _po(
        """msgid "Open"
msgstr "Aufmachen"

msgid "Save"
msgstr ""

#, fuzzy
msgctxt "part mode"
msgid "Add"
msgstr "Plus"
"""
    )
    catalog = build_catalog("de", [SHIPPED, user])
    assert catalog.gettext(None, "Open") == "Aufmachen"
    assert catalog.gettext(None, "Save") == "Speichern"
    assert catalog.gettext("part mode", "Add") == "Hinzufügen"


def test_each_entry_keeps_its_files_plural_rule():
    body = 'msgid "{count} file"\nmsgid_plural "{count} files"\nmsgstr[0] "{count} ファイル"\n'
    single_form = _po(body, "nplurals=1; plural=0;")
    catalog = build_catalog("x", [SHIPPED, single_form])
    assert catalog.ngettext(None, "{count} file", "{count} files", 5) == "{count} ファイル"
    assert catalog.ngettext(None, "Copied {count} object", "Copied {count} objects", 1) == "{count} Objekt kopiert"


def test_completeness_against_template():
    catalog = build_catalog("de", [SHIPPED])
    template = [(None, "Open"), (None, "Save"), ("part mode", "Add"), (None, "Quit")]
    assert catalog.completeness(template) == 0.75
    assert Catalog("en").completeness([]) == 1.0
