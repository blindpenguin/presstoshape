"""A small, strict reader and writer for gettext PO files.

Translation files come from users, so the reader refuses anything it doesn't understand (naming the line), limits
the size, and drops single entries whose placeholders don't match the original: a translated "{cout}" must never
turn into a crash when the message is formatted.
"""

import re
import string
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from presstoshape.i18n.plural import ENGLISH, PluralError, PluralRule, parse_plural_forms

MAX_CHARACTERS = 5 * 1024 * 1024
_KEYWORD = re.compile(r"^(msgctxt|msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+(\".*)$")
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
_WRITE_ESCAPES = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}

Field = tuple[str, str, str | None]


class PoError(ValueError):
    """A file that isn't usable PO; the message names the source and line."""


@dataclass(frozen=True)
class Entry:
    context: str | None
    message: str
    plural: str | None = None
    # One string, or one per plural form; empty strings mean untranslated.
    translations: tuple[str, ...] = ("",)
    fuzzy: bool = False
    # "path:line" places in the source, written as #: comments.
    references: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str | None, str]:
        return self.context, self.message

    @property
    def translated(self) -> bool:
        return not self.fuzzy and all(self.translations)


@dataclass(frozen=True)
class PoFile:
    header: Mapping[str, str]
    plural_rule: PluralRule
    entries: tuple[Entry, ...]
    # Why single entries were left out, e.g. 'line 120: "{cout}" isn't in the original'.
    ignored: tuple[str, ...] = ()

    @property
    def language(self) -> str | None:
        return self.header.get("Language") or None


def _unquote(text: str, where: str) -> str:
    if len(text) < 2 or not text.startswith('"') or not text.endswith('"'):
        raise PoError(f"{where}: expected a quoted string")
    body, result, index = text[1:-1], [], 0
    while index < len(body):
        character = body[index]
        if character == "\\":
            if index + 1 >= len(body) or body[index + 1] not in _ESCAPES:
                raise PoError(f"{where}: unknown escape in string")
            result.append(_ESCAPES[body[index + 1]])
            index += 2
        elif character == '"':
            raise PoError(f"{where}: unescaped quote in string")
        else:
            result.append(character)
            index += 1
    return "".join(result)


def fields(text: str) -> frozenset[Field]:
    """The str.format fields of `text` as (name, format spec, conversion); raises ValueError on bad braces."""
    parsed = string.Formatter().parse(text)
    return frozenset((name, spec or "", conversion) for _, name, spec, conversion in parsed if name is not None)


class _Builder:
    """Collects the keyword lines of one entry."""

    def __init__(self, line: int, fuzzy: bool, references: tuple[str, ...]) -> None:
        self.line = line
        self.fuzzy = fuzzy
        self.references = references
        self.values: dict[str, str] = {}
        self.last: str | None = None

    @property
    def has_translation(self) -> bool:
        return any(key.startswith("msgstr") for key in self.values)


def _parse_entries(text: str, source: str) -> list[tuple[int, Entry]]:
    entries: list[tuple[int, Entry]] = []
    current: _Builder | None = None
    fuzzy, references = False, []

    def finish() -> None:
        nonlocal current
        if current is not None:
            entries.append((current.line, _entry(current, source)))
        current = None

    for number, raw in enumerate(text.splitlines(), 1):
        where = f"{source}, line {number}"
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if line.startswith("#,"):
                fuzzy = fuzzy or "fuzzy" in (flag.strip() for flag in line[2:].split(","))
            elif line.startswith("#:"):
                references.extend(line[2:].split())
            continue
        if line.startswith('"'):
            if current is None or current.last is None:
                raise PoError(f"{where}: string continuation outside an entry")
            current.values[current.last] += _unquote(line, where)
            continue
        match = _KEYWORD.match(line)
        if match is None:
            raise PoError(f"{where}: expected msgctxt, msgid, msgid_plural or msgstr")
        keyword = match.group(1)
        starts_entry = keyword in ("msgctxt", "msgid") and (
            current is None or current.has_translation or keyword in current.values
        )
        if starts_entry:
            finish()
            current = _Builder(number, fuzzy, tuple(references))
            fuzzy, references = False, []
        if current is None:
            raise PoError(f"{where}: {keyword} before msgid")
        if keyword in current.values:
            raise PoError(f"{where}: {keyword} appears twice in one entry")
        current.values[keyword] = _unquote(match.group(3), where)
        current.last = keyword
    finish()
    return entries


def _entry(builder: _Builder, source: str) -> Entry:
    values, where = builder.values, f"{source}, line {builder.line}"
    if "msgid" not in values:
        raise PoError(f"{where}: entry without msgid")
    plural = values.get("msgid_plural")
    if plural is None:
        if set(values) - {"msgctxt", "msgid", "msgstr"} or "msgstr" not in values:
            raise PoError(f"{where}: an entry without msgid_plural needs exactly one msgstr")
        translations: tuple[str, ...] = (values["msgstr"],)
    else:
        indexed = sorted(int(key[7:-1]) for key in values if key.startswith("msgstr["))
        if "msgstr" in values or not indexed or indexed != list(range(len(indexed))):
            raise PoError(f"{where}: a plural entry needs msgstr[0], msgstr[1], ...")
        translations = tuple(values[f"msgstr[{index}]"] for index in indexed)
    return Entry(values.get("msgctxt"), values["msgid"], plural, translations, builder.fuzzy, builder.references)


def _header(text: str) -> dict[str, str]:
    header = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            header[key.strip()] = value.strip()
    return header


def _problem(entry: Entry, plural_rule: PluralRule) -> str | None:
    """Why a translated entry can't be used, or None."""
    if not any(entry.translations):
        return None
    if entry.plural is not None and len(entry.translations) != plural_rule.count:
        return f"has {len(entry.translations)} plural forms, the file's Plural-Forms says {plural_rule.count}"
    try:
        original = fields(entry.message) | (fields(entry.plural) if entry.plural is not None else frozenset())
    except ValueError:
        return None
    for translation in entry.translations:
        try:
            found = fields(translation)
        except ValueError:
            return f"has unbalanced braces in {translation!r}"
        if entry.plural is None and found != original:
            return f"placeholders {sorted(name for name, _, _ in found)} don't match the original's"
        if entry.plural is not None and not found <= original:
            return f"uses placeholders the original doesn't have in {translation!r}"
    return None


def parse_po(text: str, source: str, template: bool = False) -> PoFile:
    """Reads a PO file; a `template` (.pot) needs no Plural-Forms. Raises PoError for unusable files."""
    if len(text) > MAX_CHARACTERS:
        raise PoError(f"{source} is too large")
    header: dict[str, str] = {}
    entries: list[Entry] = []
    seen: set[tuple[str | None, str]] = set()
    raw_entries = _parse_entries(text, source)
    for line, entry in raw_entries:
        if entry.key == (None, ""):
            header = _header(entry.translations[0])
            continue
        if entry.key in seen:
            raise PoError(f"{source}, line {line}: {entry.message!r} is listed twice")
        seen.add(entry.key)
    if template:
        plural_rule = ENGLISH
    else:
        try:
            plural_rule = parse_plural_forms(header.get("Plural-Forms", ""))
        except PluralError as error:
            raise PoError(f"{source}: {error}") from None
    ignored = []
    for line, entry in raw_entries:
        if entry.key == (None, ""):
            continue
        problem = None if template else _problem(entry, plural_rule)
        if problem is None:
            entries.append(entry)
        else:
            ignored.append(f"line {line}: {entry.message!r} {problem}")
    return PoFile(header, plural_rule, tuple(entries), tuple(ignored))


def _quoted(text: str) -> str:
    return '"' + "".join(_WRITE_ESCAPES.get(character, character) for character in text) + '"'


def _entry_lines(entry: Entry, prefix: str = "") -> list[str]:
    lines = []
    if not prefix:
        lines.extend(f"#: {reference}" for reference in entry.references)
        if entry.fuzzy:
            lines.append("#, fuzzy")
    if entry.context is not None:
        lines.append(f"{prefix}msgctxt {_quoted(entry.context)}")
    lines.append(f"{prefix}msgid {_quoted(entry.message)}")
    if entry.plural is None:
        lines.append(f"{prefix}msgstr {_quoted(entry.translations[0])}")
    else:
        lines.append(f"{prefix}msgid_plural {_quoted(entry.plural)}")
        lines.extend(f"{prefix}msgstr[{index}] {_quoted(text)}" for index, text in enumerate(entry.translations))
    return lines


def write_po(header: Mapping[str, str], entries: Sequence[Entry], obsolete: Iterable[Entry] = ()) -> str:
    """PO text with the header first; `obsolete` entries are kept as #~ comments (how gettext tools do it)."""
    blocks = [['msgid ""', 'msgstr ""'] + [_quoted(f"{key}: {value}\n") for key, value in header.items()]]
    blocks.extend(_entry_lines(entry) for entry in entries)
    blocks.extend(_entry_lines(entry, "#~ ") for entry in obsolete)
    return "\n\n".join("\n".join(block) for block in blocks) + "\n"
