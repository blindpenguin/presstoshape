"""Collects the translatable texts of presstoshape/ into presstoshape.pot and merges them into the shipped .po files.

Run with `uv run python scripts/update_translations.py` after changing user-visible text; `--check` only reports
whether anything would change (the test suite runs it). Texts are found by walking the source with `ast`: literal
arguments of _(), N_(), ngettext(), pgettext() and npgettext(). A text built at runtime (f-string,
concatenation, .format()) is an error, because it could never be translated; a variable is fine (it holds a text
marked with N_() where it is defined).
"""

import argparse
import ast
import sys
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from presstoshape.i18n.po import Entry, parse_po, write_po  # noqa: E402

SOURCE = ROOT / "presstoshape"
TRANSLATIONS = SOURCE / "assets" / "translations"
TEMPLATE = TRANSLATIONS / "presstoshape.pot"
TEMPLATE_HEADER = {
    "Project-Id-Version": "PressToShape",
    "Language": "",
    "MIME-Version": "1.0",
    "Content-Type": "text/plain; charset=UTF-8",
    "Content-Transfer-Encoding": "8bit",
}
# Function name -> (context argument index or None, singular index, plural index or None).
CALLS = {
    "_": (None, 0, None),
    "N_": (None, 0, None),
    "ngettext": (None, 0, 1),
    "pgettext": (0, 1, None),
    "npgettext": (0, 1, 2),
}


# Texts built at runtime (f-strings, concatenation, .format() or % results) can't be in the template.
_BUILT_TEXT = (ast.JoinedStr, ast.BinOp, ast.Call)


class ExtractionError(Exception):
    pass


@dataclass
class _Found:
    context: str | None
    message: str
    plural: str | None
    references: list[str]
    first_use: tuple[str, int]


def _literal(node: ast.expr) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def extract(source: Path, root: Path) -> list[Entry]:
    """Template entries in order of first use (files sorted by path); raises ExtractionError listing every call
    whose texts aren't literals."""
    found: dict[tuple[str | None, str], _Found] = {}
    problems = []
    for path in sorted(source.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=relative)):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in CALLS):
                continue
            context_index, singular_index, plural_index = CALLS[node.func.id]
            indices = [index for index in (context_index, singular_index, plural_index) if index is not None]
            arguments = [node.args[index] if index < len(node.args) else None for index in indices]
            if None in arguments or node.keywords or any(isinstance(arg, _BUILT_TEXT) for arg in arguments):
                problems.append(f"{relative}:{node.lineno}: {node.func.id}() needs literal strings")
                continue
            texts = [_literal(arg) for arg in arguments]
            if None in texts:
                # A variable holding a text marked with N_() where it is defined: translated here, collected there.
                continue
            values = dict(zip(indices, texts))
            context = values.get(context_index) if context_index is not None else None
            plural = values.get(plural_index) if plural_index is not None else None
            key = (context, values[singular_index])
            # Files only, no line numbers (like xgettext --add-location=file), so moving code doesn't churn
            # the template.
            reference = relative
            position = (relative, node.lineno)
            if key in found:
                if found[key].plural != plural:
                    problems.append(f"{relative}:{node.lineno}: {key[1]!r} is used both with and without a plural")
                if reference not in found[key].references:
                    found[key].references.append(reference)
            else:
                found[key] = _Found(context, key[1], plural, [reference], position)
    if problems:
        raise ExtractionError("\n".join(problems))
    ordered = sorted(found.values(), key=lambda item: item.first_use)
    entries = []
    for item in ordered:
        empty = ("",) if item.plural is None else ("", "")
        references = tuple(item.references)
        entries.append(Entry(item.context, item.message, item.plural, empty, references=references))
    return entries


def merge(template: Iterable[Entry], po_text: str, source: str) -> str:
    """The .po text updated to the template: translations kept, new entries empty, gone ones obsolete (#~)."""
    po_file = parse_po(po_text, source)
    existing = {entry.key: entry for entry in po_file.entries}
    forms = po_file.plural_rule.count
    merged, used = [], set()
    for entry in template:
        old = existing.get(entry.key)
        if old is not None and (old.plural is None) == (entry.plural is None):
            merged.append(replace(old, plural=entry.plural, references=entry.references))
            used.add(entry.key)
        else:
            empty = ("",) if entry.plural is None else ("",) * forms
            merged.append(replace(entry, translations=empty))
    obsolete = [entry for key, entry in existing.items() if key not in used and any(entry.translations)]
    return write_po(po_file.header, merged, obsolete)


def run(check: bool) -> int:
    try:
        template = extract(SOURCE, ROOT)
    except ExtractionError as error:
        print(error, file=sys.stderr)
        return 2
    outputs = {TEMPLATE: write_po(TEMPLATE_HEADER, template)}
    for path in sorted(TRANSLATIONS.glob("*.po")):
        outputs[path] = merge(template, path.read_text(encoding="utf-8"), path.name)
    stale = [path for path, text in outputs.items() if not path.exists() or path.read_text(encoding="utf-8") != text]
    if check:
        for path in stale:
            print(f"out of date: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1 if stale else 0
    TRANSLATIONS.mkdir(parents=True, exist_ok=True)
    for path in stale:
        path.write_text(outputs[path], encoding="utf-8")
        print(f"updated {path.relative_to(ROOT)}")
    print(f"{len(template)} translatable texts")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only report whether files are out of date")
    sys.exit(run(parser.parse_args().check))
