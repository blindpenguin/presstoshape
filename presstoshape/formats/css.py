"""The CSS that SVG files from drawing programs use: `<style>` sheets with selectors (formats/css_selectors.py),
`@media` blocks for all/screen and `!important`.

Anything else (other at-rules, unsupported selectors) is skipped and counted, so the reader can say that some
rules weren't applied instead of applying them wrongly.
"""

import re
from dataclasses import dataclass, field

from presstoshape.formats.css_selectors import Node, Selector, parse_selector

_COMMENT = re.compile(r"/\*.*?(?:\*/|$)", re.S)
# Old HTML comment markers some exporters still wrap style sheets in.
_HTML_COMMENT_MARKERS = re.compile(r"<!--|-->")
_IMPORTANT = re.compile(r"!\s*important\s*$", re.I)


@dataclass(frozen=True)
class Rule:
    selector: Selector
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

    def declarations_for(self, node: Node) -> tuple[dict[str, str], dict[str, str]]:
        """(normal, important) declarations for an element, cascaded: higher specificity wins, then the later
        rule."""
        if not self.rules:
            return {}, {}
        keys = [("*", ""), ("tag", node.tag), *(("class", name) for name in node.classes)]
        if node.id is not None:
            keys.append(("id", node.id))
        candidates = [rule for key in keys for rule in self._index.get(key, ())]
        matching = sorted(
            (rule for rule in candidates if rule.selector.matches(node)),
            key=lambda rule: (rule.selector.specificity, rule.order),
        )
        normal: dict[str, str] = {}
        important: dict[str, str] = {}
        for rule in matching:
            for name, value, is_important in rule.declarations:
                (important if is_important else normal)[name] = value
        return normal, important


def _index_key(selector: Selector) -> tuple[str, str]:
    """The most selective part of the rightmost compound, so a lookup only checks rules that can match."""
    compound = selector.compounds[-1]
    if compound.ids:
        return "id", min(compound.ids)
    if compound.classes:
        return "class", min(compound.classes)
    if compound.tag is not None:
        return "tag", compound.tag
    return "*", ""


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


_MEDIA = re.compile(r"@media\b([^{]*)", re.I)
_MAX_MEDIA_DEPTH = 4


def media_applies(query: str) -> bool:
    """Whether a media query list (or a `media` attribute) holds for a screen: empty, `all` or `screen`."""
    return any(part.strip().lower() in ("", "all", "screen") for part in query.split(","))


def parse(text: str) -> Stylesheet:
    """Never raises: malformed parts are skipped and counted, the rest still applies."""
    sheet = Stylesheet()
    _parse_into(sheet, _HTML_COMMENT_MARKERS.sub(" ", _COMMENT.sub(" ", text)), 0)
    return sheet


def _parse_into(sheet: Stylesheet, text: str, depth: int) -> None:
    position = 0
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return
        brace = text.find("{", position)
        if text[position] == "@":
            semicolon = text.find(";", position)
            media = _MEDIA.match(text, position)
            if media and brace != -1 and (semicolon == -1 or brace < semicolon):
                end = _block_end(text, brace)
                if media_applies(media.group(1)) and depth < _MAX_MEDIA_DEPTH:
                    _parse_into(sheet, text[brace + 1 : end - 1 if text[end - 1 : end] == "}" else end], depth + 1)
                else:
                    sheet.skipped += 1
                position = end
                continue
            if semicolon != -1 and (brace == -1 or semicolon < brace):
                position = semicolon + 1
            else:
                position = len(text) if brace == -1 else _block_end(text, brace)
            sheet.skipped += 1
            continue
        if brace == -1:
            sheet.skipped += 1
            return
        end = _block_end(text, brace)
        prelude, body = text[position:brace], text[brace + 1 : end - 1 if text[end - 1 : end] == "}" else end]
        position = end
        # A stray `}` before the selector belongs to broken earlier input; the selector starts after it.
        prelude = prelude.rpartition("}")[2]
        selectors = [parse_selector(part) for part in _split_outside(prelude, ",")]
        if any(selector is None for selector in selectors):
            sheet.skipped += 1
        declarations = parse_declarations(body)
        if not declarations:
            continue
        for selector in selectors:
            if selector is not None:
                sheet.add(Rule(selector, declarations, len(sheet.rules)))
