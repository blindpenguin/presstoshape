"""Plural formulas from a PO header ("nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 ? 1 : 2);").

The formula is a small C expression over `n`. It comes from files users import, so it is parsed into a closure
tree by a recursive-descent parser instead of being handed to eval.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

_MAX_LENGTH = 500
_MAX_DEPTH = 50
_MAX_FORMS = 6
_TOKEN = re.compile(r"\s*(?:(\d+)|(n)|(&&|\|\||==|!=|<=|>=|[-+*/%<>!?:()]))")
_HEADER = re.compile(r"^\s*nplurals\s*=\s*(\d+)\s*;\s*plural\s*=\s*(.+?)\s*;?\s*$", re.DOTALL)

Expression = Callable[[int], int]


class PluralError(ValueError):
    """A Plural-Forms header that can't be used."""


@dataclass(frozen=True)
class PluralRule:
    count: int
    formula: Expression

    def choose(self, n: int) -> int:
        """Index of the form for `n`; out-of-range results and division by zero fall back to form 0."""
        try:
            index = self.formula(n)
        except ZeroDivisionError:
            return 0
        return index if 0 <= index < self.count else 0


ENGLISH = PluralRule(2, lambda n: int(n != 1))


def _tokens(text: str) -> list[str]:
    tokens, position = [], 0
    text = text.rstrip()
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            raise PluralError(f"unexpected {text[position:].strip()[:10]!r} in plural formula")
        tokens.append(match.group(match.lastindex))
        position = match.end()
    return tokens


def _c_division(left: int, right: int) -> int:
    # C truncates toward zero; Python floors.
    quotient = abs(left) // abs(right)
    return quotient if (left >= 0) == (right >= 0) else -quotient


def _c_remainder(left: int, right: int) -> int:
    return left - right * _c_division(left, right)


_BINARY: dict[str, Callable[[int, int], int]] = {
    "||": lambda left, right: int(bool(left) or bool(right)),
    "&&": lambda left, right: int(bool(left) and bool(right)),
    "==": lambda left, right: int(left == right),
    "!=": lambda left, right: int(left != right),
    "<": lambda left, right: int(left < right),
    ">": lambda left, right: int(left > right),
    "<=": lambda left, right: int(left <= right),
    ">=": lambda left, right: int(left >= right),
    "+": lambda left, right: left + right,
    "-": lambda left, right: left - right,
    "*": lambda left, right: left * right,
    "/": _c_division,
    "%": _c_remainder,
}
# Lowest to highest precedence; all left-associative.
_LEVELS = (("||",), ("&&",), ("==", "!="), ("<", ">", "<=", ">="), ("+", "-"), ("*", "/", "%"))


class _Parser:
    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._position = 0
        self._depth = 0

    def _peek(self) -> str | None:
        return self._tokens[self._position] if self._position < len(self._tokens) else None

    def _take(self, expected: str | None = None) -> str:
        token = self._peek()
        if token is None or (expected is not None and token != expected):
            raise PluralError(f"expected {expected or 'more'} in plural formula")
        self._position += 1
        return token

    def parse(self) -> Expression:
        expression = self._conditional()
        if self._peek() is not None:
            raise PluralError(f"unexpected {self._peek()!r} in plural formula")
        return expression

    def _conditional(self) -> Expression:
        self._depth += 1
        if self._depth > _MAX_DEPTH:
            raise PluralError("plural formula is nested too deeply")
        condition = self._binary(0)
        if self._peek() == "?":
            self._take("?")
            if_true = self._conditional()
            self._take(":")
            if_false = self._conditional()
            self._depth -= 1
            return lambda n: if_true(n) if condition(n) else if_false(n)
        self._depth -= 1
        return condition

    def _binary(self, level: int) -> Expression:
        if level == len(_LEVELS):
            return self._unary()
        left = self._binary(level + 1)
        while self._peek() in _LEVELS[level]:
            operation = _BINARY[self._take()]
            right = self._binary(level + 1)
            left = (lambda first, second, apply: lambda n: apply(first(n), second(n)))(left, right, operation)
        return left

    def _unary(self) -> Expression:
        token = self._peek()
        if token == "!":
            self._take()
            operand = self._unary()
            return lambda n: int(not operand(n))
        if token == "-":
            self._take()
            operand = self._unary()
            return lambda n: -operand(n)
        return self._primary()

    def _primary(self) -> Expression:
        token = self._take()
        if token == "n":
            return lambda n: n
        if token.isdigit():
            value = int(token)
            return lambda n: value
        if token == "(":
            inner = self._conditional()
            self._take(")")
            return inner
        raise PluralError(f"unexpected {token!r} in plural formula")


def parse_plural_forms(header: str) -> PluralRule:
    """Raises PluralError for anything but a well-formed "nplurals=N; plural=EXPR;" value."""
    if len(header) > _MAX_LENGTH:
        raise PluralError("plural formula is too long")
    match = _HEADER.match(header)
    if match is None:
        raise PluralError("Plural-Forms should look like 'nplurals=2; plural=(n != 1);'")
    count = int(match.group(1))
    if not 1 <= count <= _MAX_FORMS:
        raise PluralError(f"nplurals should be between 1 and {_MAX_FORMS}")
    return PluralRule(count, _Parser(_tokens(match.group(2))).parse())
