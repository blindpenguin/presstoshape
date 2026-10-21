"""Translations: gettext-style calls backed by PO files. Plain Python, importable from every layer.

The active catalog is module-level on purpose: App installs it once at startup, before any document or window
exists, and it is only read afterwards (a language change needs a restart). Placeholders use str.format names:
`ngettext("Copied {count} object", "Copied {count} objects", n).format(count=n)`. Pass literals only, never
f-strings, so scripts/update_translations.py can collect them.
"""

from presstoshape.i18n.catalog import Catalog

_active = Catalog("en")


def install(catalog: Catalog) -> None:
    global _active
    _active = catalog


def active_language() -> str:
    return _active.language


def user_languages() -> tuple[str, ...]:
    """The active language as a BCP 47 tag, then English, for content that offers alternatives per language."""
    tag = active_language().replace("_", "-").lower()
    return (tag, "en") if tag != "en" else ("en",)


def _(message: str) -> str:
    return _active.gettext(None, message)


def ngettext(singular: str, plural: str, count: int) -> str:
    return _active.ngettext(None, singular, plural, count)


def pgettext(context: str, message: str) -> str:
    """For short texts whose translation depends on where they appear, e.g. pgettext("part mode", "Add")."""
    return _active.gettext(context, message)


def npgettext(context: str, singular: str, plural: str, count: int) -> str:
    return _active.ngettext(context, singular, plural, count)


def N_(message: str) -> str:
    """Marks a text for translation where it is defined (registries); it is translated with _() where shown."""
    return message
