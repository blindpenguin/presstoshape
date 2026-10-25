"""Every module that dispatches on shape types must know `ImageShape`, or say why it need not (yet)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent / "presstoshape"
DISPATCH_MARKERS = ("GroupShape", "RectShape")

# Container logic, rect-only commands, or code that asks `editing/queries.py` which shapes are combinable:
# images are leaves (`children_of` is empty), never containers and have no outline to combine.
LEAF_SAFE = {
    "editing/containers.py",
    "editing/operations/_document.py",
    "editing/operations/edit_mode.py",
    "formats/svg_viewport.py",
    "geometry/masks.py",
    "render/masks.py",
    "tools/select.py",
    "tools/snapper.py",
    "editing/operations/booleans.py",
    "formats/svg_masks.py",
    # Combine accepts only paths, rectangles and ellipses.
    "editing/operations/paths.py",
}

# Real image behaviour arrives with the named task of spec svg-conformance-level5; remove the entry there.
PENDING = {}


def _dispatching_modules():
    for path in sorted(ROOT.rglob("*.py")):
        text = path.read_text()
        if any(marker in text for marker in DISPATCH_MARKERS):
            yield path.relative_to(ROOT).as_posix(), "ImageShape" in text


def test_every_dispatching_module_knows_images_or_is_listed():
    unknown = [name for name, knows in _dispatching_modules() if not knows and name not in LEAF_SAFE | PENDING.keys()]
    assert unknown == [], f"add an ImageShape case or list the module with a reason: {unknown}"


def test_listed_modules_are_not_stale():
    knows = dict(_dispatching_modules())
    stale = [name for name in LEAF_SAFE | PENDING.keys() if knows.get(name) is not False]
    assert stale == [], f"these modules handle ImageShape or no longer dispatch: {stale}"
