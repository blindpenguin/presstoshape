"""CSS selectors for `<style>` sheets: type, universal, id, class, attribute and structural pseudo-class selectors
joined by descendant, child and sibling combinators.

Parsing is a single pass over the text, matching works right to left and only walks ancestors or siblings when the
rightmost compound already matched. Pseudo-elements and anything unknown make `parse_selector` return None, so the
rule is skipped and counted instead of applied wrongly.
"""

import re
from dataclasses import dataclass
from typing import Protocol

Specificity = tuple[int, int, int]

_IDENT = re.compile(r"-?[_a-zA-Z\u0080-\U0010ffff][\w\-\u0080-\U0010ffff]*")
_ATTRIBUTE = re.compile(
    r"\s*(?P<name>[A-Za-z_][\w:.\-]*)\s*(?:(?P<op>[~|^$*]?=)\s*(?P<value>\"[^\"]*\"|'[^']*'|[^\s\]\"']+)\s*)?\]"
)
_MAX_COMPOUNDS = 16
# Pseudo-classes that never match a static drawing.
_NEVER = frozenset({"hover", "active", "focus", "visited", "target", "focus-within", "focus-visible"})
_STRUCTURAL = frozenset({"first-child", "last-child", "only-child", "root", "link"})
_WHITESPACE = " \t\n\r\f"


class Node(Protocol):
    tag: str | None
    id: str | None
    classes: frozenset[str]
    parent: "Node | None"
    previous_sibling: "Node | None"
    index: int
    sibling_count: int
    language: str | None

    def attribute(self, name: str) -> str | None: ...


@dataclass(frozen=True)
class AttributeTest:
    name: str
    operator: str | None
    value: str

    def matches(self, node: Node) -> bool:
        actual = node.attribute(self.name)
        if actual is None:
            return False
        match self.operator:
            case None:
                return True
            case "=":
                return actual == self.value
            case "~=":
                return bool(self.value) and self.value in actual.split()
            case "|=":
                return actual == self.value or actual.startswith(self.value + "-")
            case "^=":
                return bool(self.value) and actual.startswith(self.value)
            case "$=":
                return bool(self.value) and actual.endswith(self.value)
            case "*=":
                return bool(self.value) and self.value in actual
        return False


@dataclass(frozen=True)
class PseudoClass:
    kind: str
    argument: "tuple[int, int] | Compound | str | None" = None

    def matches(self, node: Node) -> bool:
        match self.kind:
            case "first-child":
                return node.index == 0
            case "last-child":
                return node.index == node.sibling_count - 1
            case "only-child":
                return node.sibling_count == 1
            case "root":
                return node.parent is None
            case "link":
                return node.tag == "a" and (node.attribute("href") or node.attribute("xlink:href")) is not None
            case "nth-child":
                step, offset = self.argument  # type: ignore[misc]
                position = node.index + 1 - offset
                return position == 0 if step == 0 else position % step == 0 and position // step >= 0
            case "not":
                return not self.argument.matches(node)  # type: ignore[union-attr]
            case "lang":
                language, wanted = (node.language or "").lower(), str(self.argument).lower()
                return bool(language) and (language == wanted or language.startswith(wanted + "-"))
        return False


@dataclass(frozen=True)
class Compound:
    """One selector without combinators: every part must match."""

    tag: str | None
    ids: frozenset[str]
    classes: frozenset[str]
    attributes: tuple[AttributeTest, ...]
    pseudo: tuple[PseudoClass, ...]
    specificity: Specificity = (0, 0, 0)

    def matches(self, node: Node) -> bool:
        if self.tag is not None and self.tag != node.tag:
            return False
        if self.ids and self.ids != {node.id}:
            return False
        if not self.classes <= node.classes:
            return False
        return all(test.matches(node) for test in self.attributes) and all(p.matches(node) for p in self.pseudo)


@dataclass(frozen=True)
class Selector:
    compounds: tuple[Compound, ...]
    # Between neighbouring compounds: " " descendant, ">" child, "+" next sibling, "~" later sibling.
    combinators: tuple[str, ...]
    specificity: Specificity = (0, 0, 0)

    def matches(self, node: Node) -> bool:
        return self._matches(len(self.compounds) - 1, node)

    def _matches(self, index: int, node: Node) -> bool:
        if not self.compounds[index].matches(node):
            return False
        if index == 0:
            return True
        combinator = self.combinators[index - 1]
        if combinator == ">":
            return node.parent is not None and self._matches(index - 1, node.parent)
        if combinator == "+":
            return node.previous_sibling is not None and self._matches(index - 1, node.previous_sibling)
        step = "parent" if combinator == " " else "previous_sibling"
        other = getattr(node, step)
        while other is not None:
            if self._matches(index - 1, other):
                return True
            other = getattr(other, step)
        return False


def parse_selector(text: str) -> Selector | None:
    """None for pseudo-elements, namespaces, unknown pseudo-classes or anything that isn't a selector."""
    text = text.strip(_WHITESPACE)
    compounds: list[Compound] = []
    combinators: list[str] = []
    position = 0
    while True:
        compound, position = _parse_compound(text, position)
        if compound is None:
            return None
        compounds.append(compound)
        start = position
        position = _skip_whitespace(text, position)
        if position >= len(text):
            break
        if text[position] in ">+~":
            combinators.append(text[position])
            position = _skip_whitespace(text, position + 1)
            if position >= len(text):
                return None
        elif position > start:
            combinators.append(" ")
        else:
            return None
        if len(compounds) >= _MAX_COMPOUNDS:
            return None
    specificity = tuple(sum(compound.specificity[level] for compound in compounds) for level in range(3))
    return Selector(tuple(compounds), tuple(combinators), specificity)  # type: ignore[arg-type]


def _skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position] in _WHITESPACE:
        position += 1
    return position


def _identifier(text: str, position: int) -> tuple[str, int] | None:
    match = _IDENT.match(text, position)
    return (match.group(), match.end()) if match else None


def _matching_paren(text: str, opening: int) -> int:
    """Index of the `)` closing the `(` at `opening`, -1 when unbalanced."""
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _parse_compound(text: str, position: int) -> tuple[Compound | None, int]:
    tag: str | None = None
    ids: set[str] = set()
    classes: set[str] = set()
    attributes: list[AttributeTest] = []
    pseudo: list[PseudoClass] = []
    specificity = [0, 0, 0]
    start = position
    if position < len(text) and text[position] == "*":
        position += 1
    elif (found := _identifier(text, position)) is not None:
        tag, position = found
        specificity[2] += 1
    while position < len(text):
        char = text[position]
        if char in "#.":
            found = _identifier(text, position + 1)
            if found is None:
                return None, position
            (ids if char == "#" else classes).add(found[0])
            specificity[0 if char == "#" else 1] += 1
            position = found[1]
        elif char == "[":
            match = _ATTRIBUTE.match(text, position + 1)
            if match is None:
                return None, position
            value = match.group("value") or ""
            attributes.append(AttributeTest(match.group("name"), match.group("op"), value.strip("\"'")))
            specificity[1] += 1
            position = match.end()
        elif char == ":":
            parsed = _parse_pseudo(text, position + 1)
            if parsed is None:
                return None, position
            item, position = parsed
            pseudo.append(item)
            inner = item.argument.specificity if item.kind == "not" else (0, 1, 0)  # type: ignore[union-attr]
            specificity = [total + part for total, part in zip(specificity, inner)]
        else:
            break
    if position == start:
        return None, position
    return Compound(
        tag, frozenset(ids), frozenset(classes), tuple(attributes), tuple(pseudo), tuple(specificity)
    ), position  # type: ignore[arg-type]


def _parse_pseudo(text: str, position: int) -> tuple[PseudoClass, int] | None:
    found = _identifier(text, position)
    if found is None:
        return None
    name, position = found
    name = name.lower()
    if position < len(text) and text[position] == "(":
        closing = _matching_paren(text, position)
        if closing == -1:
            return None
        argument, end = text[position + 1 : closing].strip(), closing + 1
        if name == "nth-child":
            step_offset = _parse_nth(argument)
            return (PseudoClass(name, step_offset), end) if step_offset is not None else None
        if name == "not":
            inner, stop = _parse_compound(argument, 0)
            if inner is None or stop != len(argument):
                return None
            return PseudoClass(name, inner), end
        if name == "lang" and _IDENT.fullmatch(argument):
            return PseudoClass(name, argument), end
        return None
    if name in _STRUCTURAL:
        return PseudoClass(name), position
    if name in _NEVER:
        return PseudoClass("never"), position
    return None


def _parse_nth(argument: str) -> tuple[int, int] | None:
    argument = argument.lower().replace(" ", "")
    if argument == "odd":
        return 2, 1
    if argument == "even":
        return 2, 0
    try:
        if "n" not in argument:
            return 0, int(argument)
        step_text, _, offset_text = argument.partition("n")
        step = {"": 1, "+": 1, "-": -1}.get(step_text)
        if step is None:
            step = int(step_text)
        if offset_text and offset_text[0] not in "+-":
            return None
        return step, int(offset_text) if offset_text else 0
    except ValueError:
        return None
