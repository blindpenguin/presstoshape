"""Dev-only: renders the main window once offscreen and saves a PNG, for visual review without a human
watching the window. Seeds a few demo shapes unless `--empty` is passed; `--tool rectangle` (etc.) activates a
tool first, e.g. to check its options panel; `--images` adds a picture and a reference image.

Usage: uv run python scripts/screenshot_app.py [--empty] [--images] [--tool NAME] [--language CODE]
Output: dev-screenshots/app.png (gitignored)
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from presstoshape.app import App  # noqa: E402
from presstoshape.editing.operations import images, selection, shapes, style, transform, view  # noqa: E402
from presstoshape.editing.session import Session  # noqa: E402
from presstoshape.models.app_state import Tool  # noqa: E402

_OUTPUT = Path(__file__).resolve().parent.parent / "dev-screenshots" / "app.png"


def _seed(session: Session) -> None:
    a = shapes.add_rectangle(session, (60, 60), (260, 200))
    b = shapes.add_ellipse(session, (200, 120), (360, 280))
    style.set_stroke_width(session, 4)
    style.set_stroke(session, "#7c3aed")
    shapes.add_path(session, [(40, 330), (140, 250), (240, 360), (360, 300), (540, 360)])
    text = shapes.add_text(session, (390, 90), "PressToShape")
    transform.set_rotation(session, text, -12)
    selection.set_selection(session, {a, b})


def _demo_picture() -> bytes:
    import skia

    surface = skia.Surface(240, 160)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorWHITE)
    colors = (skia.ColorRED, skia.ColorGREEN, skia.ColorBLUE, skia.ColorYELLOW)
    for index, color in enumerate(colors):
        canvas.drawRect(skia.Rect.MakeXYWH(index % 2 * 120, index // 2 * 80, 120, 80), skia.Paint(Color=color))
    return surface.makeImageSnapshot().encodeToData(skia.EncodedImageFormat.kPNG, 100).bytes()


def _seed_images(session: Session) -> None:
    picture = _demo_picture()
    images.place_images(session, [("reference.png", picture)], (300, 200), reference=True)
    images.place_images(session, [("photo.png", picture)], (440, 260))


if __name__ == "__main__":
    language = sys.argv[sys.argv.index("--language") + 1] if "--language" in sys.argv else "en"
    app = App(language=language)
    if "--empty" not in sys.argv:
        _seed(app.session)
    if "--images" in sys.argv:
        _seed_images(app.session)
    if "--tool" in sys.argv:
        view.select_tool(app.session, Tool[sys.argv[sys.argv.index("--tool") + 1].upper()])
    app.run(screenshot_path=_OUTPUT)
    print(_OUTPUT)
