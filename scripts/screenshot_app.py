"""Dev-only: renders the main window once offscreen and saves a PNG, for visual review without a human
watching the window. Seeds a few demo shapes unless `--empty` is passed.

Usage: uv run python scripts/screenshot_app.py [--empty]
Output: dev-screenshots/app.png (gitignored)
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from veccy.app import App  # noqa: E402
from veccy.controllers.app_controller import AppController  # noqa: E402

_OUTPUT = Path(__file__).resolve().parent.parent / "dev-screenshots" / "app.png"


def _seed(c: AppController) -> None:
    a = c.add_rectangle((60, 60), (260, 200))
    b = c.add_ellipse((200, 120), (360, 280))
    c.set_stroke_width(4)
    c.set_stroke("#7c3aed")
    c.add_path([(40, 330), (140, 250), (240, 360), (360, 300), (540, 360)])
    c.add_text((390, 90), "veccy")
    c.set_selection({a, b})


if __name__ == "__main__":
    app = App()
    if "--empty" not in sys.argv:
        _seed(app.controller)
    app.run(screenshot_path=_OUTPUT)
    print(_OUTPUT)
