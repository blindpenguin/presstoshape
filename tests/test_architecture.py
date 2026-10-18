"""Layer rules: which veccy packages may import which, and where Qt is allowed. Checked statically with ast."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "veccy"

# Package (or top-level module) -> veccy packages/modules it may import.
ALLOWED = {
    "models": set(),
    "geometry": {"models"},
    "formats": {"models", "geometry"},
    "render": {"models", "geometry"},
    "editing": {"models", "geometry", "formats", "render"},
    "tools": {"models", "geometry", "render", "editing"},
    "views": {"models", "geometry", "formats", "render", "editing", "tools", "icons"},
    "app": {"editing", "views"},
    "icons": set(),
}

QT_FREE = {"models", "geometry", "formats", "render", "editing", "tools"}


def _modules() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.py") if path != ROOT / "__init__.py")


def _layer(path: Path) -> str:
    return path.relative_to(ROOT).with_suffix("").parts[0]


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
    return found


def _violations() -> list[str]:
    problems = []
    for path in _modules():
        layer = _layer(path)
        allowed = ALLOWED[layer]
        where = path.relative_to(ROOT.parent)
        for line, module in _imports(path):
            top, _, rest = module.partition(".")
            if top == "PySide6" and layer in QT_FREE:
                problems.append(f"{where}:{line}: Qt import {module!r} in Qt-free layer {layer!r}")
            if top == "veccy" and rest:
                target = rest.split(".")[0]
                if target != layer and target not in allowed:
                    problems.append(f"{where}:{line}: {layer!r} must not import {module!r}")
    return problems


def test_every_layer_has_rules():
    assert {_layer(path) for path in _modules()} <= set(ALLOWED)


def test_imports_follow_layer_rules():
    assert _violations() == []
