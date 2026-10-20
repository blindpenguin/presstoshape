"""The small part of CSS that SVG files from drawing programs use: `<style>` sheets with type, class, id and
universal selectors (alone, compound like `path.st0`, or in comma lists) and `!important`.

Anything else (combinators, attribute selectors, pseudo-classes, at-rules) is skipped and counted, so the
reader can say that some rules weren't applied instead of applying them wrongly.
"""

import re
from dataclasses import dataclass, field

_COMMENT = re.compile(r"/\*.*?(?:\*/|$)", re.S)
# Old HTML comment markers some exporters still wrap style sheets in.
_HTML_COMMENT_MARKERS = re.compile(r"<!--|-->")
_COMPOUND = re.compile(r"(?P<tag>\*|[A-Za-z_][\w-]*)?(?P<rest>(?:[.#][A-Za-z_-][\w-]*)*)")
_SIMPLE = re.compile(r"([.#])([\w-]+)")
_IMPORTANT = re.compile(r"!\s*important\s*$", re.I)

Specificity = tuple[int, int, int]


@dataclass(frozen=True)
class Compound:
    """One selector without combinators: an optional type (None = any) plus ids and classes that must all
    match."""

    tag: str | None
    ids: frozenset[str]
    classes: frozenset[str]

    def matches(self, tag: str, element_id: str | None, classes: frozenset[str]) -> bool:
        if self.tag is not None and self.tag != tag:
            return False
        if self.ids and (element_id is None or self.ids != {element_id}):
            return False
        return self.classes <= classes

    @property
    def specificity(self) -> Specificity:
        return len(self.ids), len(self.classes), 0 if self.tag is None else 1


@dataclass(frozen=True)
class Rule:
    selector: Compound
    # (property, value, important), in source order.
    declarations: tuple[tuple[str, str, bool], ...]
    order: int


@dataclass
class Stylesheet:
    rules: list[Rule] = field(default_factory=list)
    # Rules and at-rules dropped because they use syntax this reader doesn't support.
    skipped: int = 0
    _index: dict[tuple[str, str], list[Rule]] = field(default_factory=dict, repr=False)

    def add(self, rule: Rule) -> None:
        self.rules.append(rule)
        self._index.setdefault(_index_key(rule.selector), []).append(rule)

    def declarations_for(
        self, tag: str, element_id: str | None, classes: frozenset[str]
    ) -> tuple[dict[str, str], dict[str, str]]:
        """(normal, important) declarations for an element, cascaded: higher specificity wins, then the later
        rule."""
        if not self.rules:
            return {}, {}
        keys = [("*", ""), ("tag", tag), *(("class", name) for name in classes)]
        if element_id is not None:
            keys.append(("id", element_id))
        candidates = [rule for key in keys for rule in self._index.get(key, ())]
        matching = sorted(
            (rule for rule in candidates if rule.selector.matches(tag, element_id, classes)),
            key=lambda rule: (rule.selector.specificity, rule.order),
        )
        normal: dict[str, str] = {}
        important: dict[str, str] = {}
        for rule in matching:
            for name, value, is_important in rule.declarations:
                (important if is_important else normal)[name] = value
        return normal, important


def _index_key(selector: Compound) -> tuple[str, str]:
    """The most selective part, so a lookup only checks rules that can match."""
    if selector.ids:
        return "id", min(selector.ids)
    if selector.classes:
        return "class", min(selector.classes)
    if selector.tag is not None:
        return "tag", selector.tag
    return "*", ""


def parse_selector(text: str) -> Compound | None:
    """A compound selector, or None when it uses anything unsupported (or isn't a selector at all)."""
    text = text.strip()
    match = _COMPOUND.fullmatch(text)
    if not text or match is None:
        return None
    tag = match.group("tag")
    parts = _SIMPLE.findall(match.group("rest"))
    return Compound(
        None if tag in (None, "*") else tag,
        frozenset(name for kind, name in parts if kind == "#"),
        frozenset(name for kind, name in parts if kind == "."),
    )


def parse_declarations(text: str) -> tuple[tuple[str, str, bool], ...]:
    """`name: value` pairs split on `;` outside parentheses and quotes; `!important` is stripped and flagged.
    Also used for inline `style` attributes."""
    declarations = []
    for chunk in _split_outside(text, ";"):
        name, colon, value = chunk.partition(":")
        name, value = name.strip().lower(), value.strip()
        if not colon or not name or not value:
            continue
        important = _IMPORTANT.search(value)
        if important:
            value = value[: important.start()].strip()
            if not value:
                continue
        declarations.append((name, value, important is not None))
    return tuple(declarations)


def _split_outside(text: str, separator: str) -> list[str]:
    chunks, depth, quote, start = [], 0, "", 0
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == separator and depth == 0:
            chunks.append(text[start:index])
            start = index + 1
    chunks.append(text[start:])
    return chunks


def _block_end(text: str, opening: int) -> int:
    """Index just past the `}` closing the block opened at `opening` (end of text when unbalanced)."""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    return len(text)


def parse(text: str) -> Stylesheet:
    """Never raises: malformed parts are skipped and counted, the rest still applies."""
    text = _HTML_COMMENT_MARKERS.sub(" ", _COMMENT.sub(" ", text))
    sheet = Stylesheet()
    position = 0
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return sheet
        brace = text.find("{", position)
        if text[position] == "@":
            semicolon = text.find(";", position)
            if semicolon != -1 and (brace == -1 or semicolon < brace):
                position = semicolon + 1
            else:
                position = len(text) if brace == -1 else _block_end(text, brace)
            sheet.skipped += 1
            continue
        if brace == -1:
            sheet.skipped += 1
            return sheet
        end = _block_end(text, brace)
        prelude, body = text[position:brace], text[brace + 1 : end - 1 if text[end - 1 : end] == "}" else end]
        position = end
        # A stray `}` before the selector belongs to broken earlier input; the selector starts after it.
        prelude = prelude.rpartition("}")[2]
        selectors = [parse_selector(part) for part in prelude.split(",")]
        if any(selector is None for selector in selectors):
            sheet.skipped += 1
        declarations = parse_declarations(body)
        if not declarations:
            continue
        for selector in selectors:
            if selector is not None:
                sheet.add(Rule(selector, declarations, len(sheet.rules)))
