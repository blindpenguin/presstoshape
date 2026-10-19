# Translating PressToShape

PressToShape ships in English and German. The English texts in the source are British English. You can add another language, or fix and complete an existing one, with a translation file. No programming and no new PressToShape release are needed.

## How translations work

- Translations are gettext **PO files** (`.po`): plain text, one entry per piece of interface text. Common tools can edit them, for example [Poedit](https://poedit.net/), Lokalize, or any text editor.
- Each file is named after its language code: `fr.po` (French), `pt_BR.po` (Brazilian Portuguese), `de.po` (German).
- PressToShape looks for your files in a **translations folder**. Settings → Language → Open folder shows it:
  - Linux: `~/.local/share/PressToShape/PressToShape/translations/`
  - Windows (installed): `%LOCALAPPDATA%\PressToShape\PressToShape\translations\`
  - Portable Windows build: the `translations` folder next to `PressToShape.exe`
- Your file wins over the shipped one entry by entry. Anything your file doesn't translate falls back to the shipped translation, then to English, so an incomplete file is fine.
- The chosen language applies after restarting PressToShape.

## Start a new language

1. In PressToShape, open **Edit → Settings → Language** and click **Save template…**. This saves `presstoshape.pot`, the list of every text in the interface. In the source code it is `presstoshape/assets/translations/presstoshape.pot`.
2. Create a new translation from the template. In Poedit: File → New from POT/PO file, then pick your language. Poedit fills in the `Language` and `Plural-Forms` headers for you.
3. Translate, save as `<code>.po` (for example `fr.po`).
4. In Settings → Language, click **Import…** and pick the file. Then choose the language in the list and restart PressToShape.

You can also copy the file into the translations folder yourself; it's picked up on the next start.

## Rules for translators

- **Placeholders** in braces, like `{count}` or `{name}`, must stay exactly as they are (you may move them). An entry whose placeholders don't match the original is ignored and shows the original text instead. Import tells you which entries were ignored and why.
  - In plural forms you may leave a placeholder out, e.g. `"Ein Objekt kopiert"` for one object.
  - Keep format details like `{angle:.1f}` unchanged.
- **Plural forms** need the `Plural-Forms` header for your language (for example `nplurals=2; plural=(n != 1);`). A file without it can't be imported.
- **Menu letters**: the `&` marks the letter you can press with Alt to open a menu or pick a menu entry (`&File` is opened with Alt+F). Choose letters that are unique within the same menu.
- **Context**: some short words appear in different places with different meanings. Those entries carry a context (`msgctxt`), for example `part mode` for the Composite part modes and `tool` for tool names.
- Entries marked **fuzzy** count as untranslated.

## Updating a translation after a new version

New PressToShape versions may add or change texts. Save the new template from Settings and use your editor's "update from POT" (Poedit: Catalog → Update from POT file). New texts appear untranslated; your existing translations stay.

## For developers

- Mark every user-visible text in the source:
  - `_("text")` for a text shown where it is written;
  - `ngettext("{count} object", "{count} objects", count).format(count=count)` for counts;
  - `pgettext("context", "text")` for short, ambiguous words;
  - `N_("text")` where a text is defined but shown elsewhere (registries, label tables), translated there with `_(label)`.
- Pass literals only. f-strings, concatenation and `.format()` inside these calls can't be collected; put named placeholders in the text and call `.format()` on the result.
- After changing texts, run `uv run python scripts/update_translations.py`. It regenerates the template and merges it into the shipped `.po` files. The test suite fails while the template is out of date, and while `de.po` isn't complete.
- Don't name a variable `_` in a function that translates: it would hide the translation function.
- Not translated: log messages, ids, file format keys, keyboard shortcuts.
