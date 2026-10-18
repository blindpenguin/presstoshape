"""Dev-only: renders the main window once offscreen and saves a PNG, for visual review without a human
watching the window. Seeds a few demo shapes unless `--empty` is passed; `--tool rectangle` (etc.) activates a
tool first, e.g. to check its options panel.

Usage: uv run python scripts/screenshot_app.py [--empty] [--tool NAME]
Output: dev-screenshots/app.png (gitignored)
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veccy.app import App  # noqa: E402
from veccy.editing.operations import selection, shapes, style, transform, view  # noqa: E402
from veccy.editing.session import Session  # noqa: E402
from veccy.models.app_state import Tool  # noqa: E402

_OUTPUT = Path(__file__).resolve().parent.parent / "dev-screenshots" / "app.png"


def _seed(session: Session) -> None:
    a = shapes.add_rectangle(session, (60, 60), (260, 200))
    b = shapes.add_ellipse(session, (200, 120), (360, 280))
    style.set_stroke_width(session, 4)
    style.set_stroke(session, "#7c3aed")
    shapes.add_path(session, [(40, 330), (140, 250), (240, 360), (360, 300), (540, 360)])
    text = shapes.add_text(session, (390, 90), "veccy")
    transform.set_rotation(session, text, -12)
    selection.set_selection(session, {a, b})


if __name__ == "__main__":
    app = App()
    if "--empty" not in sys.argv:
        _seed(app.session)
    if "--tool" in sys.argv:
        view.select_tool(app.session, Tool[sys.argv[sys.argv.index("--tool") + 1].upper()])
    app.run(screenshot_path=_OUTPUT)
    print(_OUTPUT)
