"""One language's translations merged into a lookup table: shipped file first, user file entry by entry over it."""

from collections.abc import Iterable, Sequence

from presstoshape.i18n.plural import ENGLISH, PluralRule
from presstoshape.i18n.po import PoFile

Key = tuple[str | None, str]


class Catalog:
    """Translations of one language; anything missing comes back as the English source text."""

    def __init__(self, language: str, table: dict[Key, tuple[tuple[str, ...], PluralRule]] | None = None) -> None:
        self.language = language
        self._table = table or {}

    def gettext(self, context: str | None, message: str) -> str:
        found = self._table.get((context, message))
        return found[0][0] if found is not None else message

    def ngettext(self, context: str | None, singular: str, plural: str, count: int) -> str:
        found = self._table.get((context, singular))
        if found is None:
            return singular if ENGLISH.choose(count) == 0 else plural
        forms, rule = found
        return forms[rule.choose(count)]

    def completeness(self, template: Iterable[Key]) -> float:
        """Share of the template's entries this catalog translates, 0..1."""
        keys = list(template)
        return sum(key in self._table for key in keys) / len(keys) if keys else 1.0


def build_catalog(language: str, files: Sequence[PoFile]) -> Catalog:
    """`files` from lowest to highest priority; untranslated and fuzzy entries never replace a translation."""
    table: dict[Key, tuple[tuple[str, ...], PluralRule]] = {}
    for po_file in files:
        for entry in po_file.entries:
            if entry.translated:
                table[entry.key] = (entry.translations, po_file.plural_rule)
    return Catalog(language, table)
