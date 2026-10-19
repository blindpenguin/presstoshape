"""Which languages are available (English, shipped files, user files) and which one to use."""

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from presstoshape.i18n.catalog import Catalog, build_catalog
from presstoshape.i18n.po import PoError, PoFile, parse_po

ENGLISH = "en"
# The source texts are British English, so English uses the UK locale (names, number and date formats).
ENGLISH_LOCALE = "en_GB"
LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(_[A-Z]{2})?$")
SHIPPED_FOLDER = Path(__file__).resolve().parent.parent / "assets" / "translations"
TEMPLATE = SHIPPED_FOLDER / "presstoshape.pot"

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Language:
    code: str
    shipped: Path | None = None
    user: Path | None = None


def _read(path: Path) -> PoFile | None:
    try:
        return parse_po(path.read_text(encoding="utf-8"), path.name)
    except (OSError, UnicodeDecodeError, PoError) as error:
        _log.warning("Skipping translation %s: %s", path, error)
        return None


def _po_files(folder: Path | None) -> dict[str, Path]:
    if folder is None or not folder.is_dir():
        return {}
    return {path.stem: path for path in sorted(folder.glob("*.po")) if LANGUAGE_CODE.match(path.stem)}


def template_keys(template: Path = TEMPLATE) -> list[tuple[str | None, str]]:
    try:
        return [entry.key for entry in parse_po(template.read_text(encoding="utf-8"), template.name, True).entries]
    except (OSError, PoError) as error:
        _log.warning("Can't read the translation template %s: %s", template, error)
        return []


def load_catalog(language: Language) -> Catalog:
    """The language's catalog; unreadable files are skipped (logged), so the worst case is English text."""
    files = [po_file for path in (language.shipped, language.user) if path and (po_file := _read(path))]
    return build_catalog(language.code, files)


def locale_name(code: str) -> str:
    """The Qt/system locale for a language code: British English for English, the code itself otherwise."""
    return ENGLISH_LOCALE if code == ENGLISH else code


def available_languages(user_folder: Path | None, shipped_folder: Path = SHIPPED_FOLDER) -> list[Language]:
    """English first, then every language with a shipped or user file, by code."""
    shipped, user = _po_files(shipped_folder), _po_files(user_folder)
    others = sorted((shipped.keys() | user.keys()) - {ENGLISH})
    return [Language(ENGLISH), *(Language(code, shipped.get(code), user.get(code)) for code in others)]


def resolve(saved: str | None, system_languages: Sequence[str], available: Sequence[Language]) -> str:
    """The saved language if still available, else the first system language that is (exactly or by its
    language part, "de_AT" -> "de"), else English. System names may use "-" ("de-DE", as Qt reports them)."""
    codes = {language.code for language in available}
    if saved in codes:
        return saved
    for system_language in system_languages:
        name = system_language.replace("-", "_")
        if name in codes:
            return name
        if name.split("_")[0] in codes:
            return name.split("_")[0]
    return ENGLISH


def code_for_import(file_name: str, header_language: str | None) -> str | None:
    """Language code for an imported file: its name ("fr.po"), else its Language header, else None."""
    stem = Path(file_name).stem
    if LANGUAGE_CODE.match(stem):
        return stem
    if header_language and LANGUAGE_CODE.match(header_language.replace("-", "_")):
        return header_language.replace("-", "_")
    return None
