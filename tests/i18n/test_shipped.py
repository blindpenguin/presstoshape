from presstoshape.editing.operations import clipboard, selection, shapes
from presstoshape.editing.session import Session
from presstoshape.i18n import _, ngettext, pgettext
from presstoshape.i18n.languages import SHIPPED_FOLDER, TEMPLATE, Language, load_catalog, template_keys
from presstoshape.i18n.po import parse_po


def test_german_parses_cleanly_and_is_complete():
    german = parse_po((SHIPPED_FOLDER / "de.po").read_text(encoding="utf-8"), "de.po")
    assert german.ignored == ()
    assert german.language == "de"
    catalog = load_catalog(Language("de", shipped=SHIPPED_FOLDER / "de.po"))
    assert catalog.completeness(template_keys(TEMPLATE)) == 1.0


def test_german_texts_and_plurals(german):
    assert _("&File") == "&Datei"
    assert pgettext("part mode", "Add") == "Hinzufügen"
    assert ngettext("{count} object", "{count} objects", 1).format(count=1) == "1 Objekt"
    assert ngettext("{count} object", "{count} objects", 3).format(count=3) == "3 Objekte"


def test_operations_report_in_german(german):
    session = Session()
    assert session.state.document.layers[0].name == "Ebene 1"
    assert session.state.status_message == "Bereit"
    first = shapes.add_rectangle(session, (0, 0), (10, 10))
    second = shapes.add_rectangle(session, (20, 0), (30, 10))
    selection.set_selection(session, {first, second})
    clipboard.copy_selection(session)
    assert session.state.status_message == "2 Objekte kopiert"
    selection.delete_selection(session)
    assert session.undo_label == "2 Objekte löschen"
