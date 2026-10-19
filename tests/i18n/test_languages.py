import logging

from presstoshape.i18n.languages import Language, available_languages, code_for_import, load_catalog, resolve

HEADER = 'msgid ""\nmsgstr ""\n"Plural-Forms: nplurals=2; plural=(n != 1);\\n"\n\n'


def _write(folder, name, body):
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def _setup(tmp_path):
    shipped, user = tmp_path / "shipped", tmp_path / "user"
    _write(shipped, "de.po", 'msgid "Open"\nmsgstr "Öffnen"\n\nmsgid "Save"\nmsgstr "Speichern"\n')
    _write(user, "de.po", 'msgid "Open"\nmsgstr "Aufmachen"\n')
    _write(user, "fr.po", 'msgid "Open"\nmsgstr "Ouvrir"\n')
    _write(user, "not a code.po", "")
    return shipped, user


def test_discovery_merges_shipped_and_user_files(tmp_path):
    shipped, user = _setup(tmp_path)
    languages = available_languages(user, shipped)
    assert [language.code for language in languages] == ["en", "de", "fr"]
    _english, german, french = languages
    assert (german.shipped, german.user) == (shipped / "de.po", user / "de.po")
    assert (french.shipped, french.user) == (None, user / "fr.po")
    assert load_catalog(german).gettext(None, "Open") == "Aufmachen"
    assert load_catalog(german).gettext(None, "Save") == "Speichern"


def test_missing_user_folder_is_fine(tmp_path):
    shipped, _ = _setup(tmp_path)
    assert [language.code for language in available_languages(None, shipped)] == ["en", "de"]
    assert [language.code for language in available_languages(tmp_path / "nope", shipped)] == ["en", "de"]


def test_broken_user_file_is_skipped_with_a_warning(tmp_path, caplog):
    shipped, user = _setup(tmp_path)
    (user / "de.po").write_text("this is not PO")
    with caplog.at_level(logging.WARNING):
        catalog = load_catalog(Language("de", shipped / "de.po", user / "de.po"))
    assert catalog.gettext(None, "Open") == "Öffnen"
    assert "Skipping translation" in caplog.text


def test_resolve_order():
    available = [Language("en"), Language("de"), Language("pt_BR")]
    assert resolve("de", ["fr"], available) == "de"
    assert resolve("fr", ["de-AT", "en-US"], available) == "de"
    assert resolve(None, ["pt-BR"], available) == "pt_BR"
    assert resolve(None, ["ja-JP", "ja"], available) == "en"
    assert resolve(None, [], available) == "en"


def test_code_for_import():
    assert code_for_import("/x/fr.po", None) == "fr"
    assert code_for_import("pt_BR.po", None) == "pt_BR"
    assert code_for_import("presstoshape-fr.po", "fr") == "fr"
    assert code_for_import("translation.po", "pt-BR") == "pt_BR"
    assert code_for_import("../../evil.po", "../x") is None
    assert code_for_import("translation.po", None) is None
