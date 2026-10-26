"""Code conventions from CLAUDE.md that can be checked statically with ast."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "presstoshape"
OPERATIONS = ROOT / "editing" / "operations"

# (module, top-level function) -> why it may touch `layer.shapes` instead of going through `editing/containers.py`.
DIRECT_LAYER_ACCESS = {
    ("_document", "add_on_top"): "active layer when no container is entered",
    ("shapes", "_add"): "active layer when no container is entered",
    ("documents", "save_file"): "counts reference images in the whole document",
    ("images", "place_images"): "reference images always go to the Reference layer",
    ("images", "_unlock_emptied_reference_layers"): "looks at whole layers",
    ("recovery", "_preview"): "collects media of the whole document",
}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(), filename=str(path))


def _is_path_like(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return isinstance(node.value, str)
    if isinstance(node, (ast.JoinedStr, ast.BinOp)):
        return True
    if isinstance(node, ast.Attribute):
        return isinstance(node.value, ast.Name) and node.value.id == "icons"
    if isinstance(node, ast.Call):
        return isinstance(node.func, ast.Name) and node.func.id in {"str", "Path", "fspath"}
    return False


def _qicon_from_paths() -> list[str]:
    problems = []
    for path in sorted(ROOT.rglob("*.py")):
        for node in ast.walk(_tree(path)):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", None)
            if name == "QIcon" and _is_path_like(node.args[0]):
                problems.append(f"{path.relative_to(ROOT.parent)}:{node.lineno}")
    return problems


def _layer_shapes_access() -> set[tuple[str, str]]:
    found = set()
    for path in sorted(OPERATIONS.glob("*.py")):
        for top in _tree(path).body:
            if any(isinstance(node, ast.Attribute) and node.attr == "shapes" for node in ast.walk(top)):
                found.add((path.stem, getattr(top, "name", f"line {top.lineno}")))
    return found


def test_icons_load_through_the_icon_engine():
    """QIcon(path) leaves `currentColor` black; SVG icons go through `views.icon_engine.icon(path)`."""
    assert _qicon_from_paths() == []


def test_operations_reach_shapes_through_containers():
    """Operations work on `containers.pickable_shapes` / `change_container`, so they also work inside groups and
    Composites. A new direct `.shapes` access needs an entry in DIRECT_LAYER_ACCESS saying why."""
    assert _layer_shapes_access() == set(DIRECT_LAYER_ACCESS)
